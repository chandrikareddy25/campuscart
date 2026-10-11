from decimal import Decimal
from html import escape
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg
from psycopg.types.json import Jsonb
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db import connect
from app.services import notify


def require_paid(order):
    if order.get('payment_status') != 'paid':
        raise HTTPException(
            409,
            'Record payment in Admin → Orders before collection',
        )


def payment_info(row):
    if not row:
        return None

    return {
        key: row[key]
        for key in ('amount', 'method', 'reference', 'created_at')
    } | {
        'receipt_number': f"CC-R-{row['id']:06d}"
    }


def load_order(conn, order_id, user, lock=False):
    sql = 'SELECT * FROM orders WHERE id=%s'
    if lock:
        sql += ' FOR UPDATE'

    order = conn.execute(sql, (order_id,)).fetchone()

    if not order or (
        user['role'] != 'admin' and order['user_id'] != user['id']
    ):
        raise HTTPException(404, 'Order not found')

    return order


def make_bill(conn, order):
    items = conn.execute(
        '''
        SELECT product_name, quantity, unit_price
        FROM order_items
        WHERE order_id=%s
        ORDER BY id
        ''',
        (order['id'],),
    ).fetchall()

    payment = conn.execute(
        'SELECT * FROM order_payments WHERE order_id=%s',
        (order['id'],),
    ).fetchone()

    return {
        'order_id': order['id'],
        'total': order['total'],
        'currency': 'INR',
        'status': order['status'],
        'payment_status': order['payment_status'],
        'items': items,
        'payment': payment_info(payment),
    }


class PaymentInput(BaseModel):
    model_config = ConfigDict(extra='forbid')

    method: Literal['cash', 'upi']
    reference: str = Field(default='', max_length=100)
    confirmed: Literal[True]

    @model_validator(mode='after')
    def clean(self):
        self.reference = self.reference.strip().upper()

        if self.method == 'upi' and len(self.reference) < 3:
            raise ValueError('Enter the verified UPI transaction reference')

        if self.method == 'cash':
            self.reference = ''

        return self


def render_receipt(payment):
    snapshot = payment['snapshot']

    rows = ''.join(
        '<tr><td>' + escape(item['name']) +
        '</td><td>' + str(item['quantity']) +
        '</td><td>₹' + item['unit_price'] +
        '</td><td>₹' + item['line_total'] + '</td></tr>'
        for item in snapshot['items']
    )

    paid_at = payment['created_at'].astimezone(
        ZoneInfo('Asia/Kolkata')
    ).strftime('%d %b %Y, %I:%M %p IST')

    reference = escape(payment['reference'] or '—')

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CampusCart receipt</title>
<style>
body {{
    font: 15px system-ui;
    color: #182538;
    max-width: 760px;
    margin: 40px auto;
    padding: 20px;
}}
h1 {{ font-size: 32px; }}
table {{
    width: 100%;
    border-collapse: collapse;
    margin: 28px 0;
}}
th, td {{
    text-align: left;
    padding: 12px 8px;
    border-bottom: 1px solid #ddd;
    overflow-wrap: anywhere;
}}
.total {{
    font-size: 24px;
    font-weight: 700;
    text-align: right;
}}
.paid {{ color: #426d25; font-weight: 700; }}
small {{ color: #69756a; }}
@media print {{
    body {{ margin: 0; }}
    .print-help {{ display: none; }}
}}
</style>
</head>
<body>
<small>CAMPUSCART · PAYMENT RECEIPT</small>
<h1>{escape(snapshot['university'])}</h1>
<p>
<b>Receipt:</b> CC-R-{payment['id']:06d}<br>
<b>Order:</b> {escape(snapshot['order_id'])}<br>
<b>Student:</b> {escape(snapshot['customer_name'])}<br>
<b>Collection:</b> {escape(snapshot['pickup_name'])}
</p>
<table>
<thead>
<tr><th>Item</th><th>Qty</th><th>Unit price</th><th>Amount</th></tr>
</thead>
<tbody>{rows}</tbody>
</table>
<p class="total">Total received: ₹{snapshot['total']}</p>
<p class="paid">PAID · {escape(payment['method'].upper())}</p>
<p>
Recorded: {paid_at}<br>
Transaction reference: {reference}
</p>
<small>
Payment received at campus pickup and recorded by an administrator.
Amounts are the saved order prices; no additional tax or fee is calculated.
</small>
<p class="print-help">
Use your browser's Print command to print this receipt or save it as PDF.
</p>
</body>
</html>'''


def create_billing_router(current_user, admin):
    router = APIRouter()

    @router.get('/api/orders/{order_id}/billing')
    def bill(order_id: UUID, user=Depends(current_user)):
        with connect() as conn:
            return make_bill(conn, load_order(conn, order_id, user))

    @router.post('/api/admin/orders/{order_id}/payment')
    def record_payment(
        order_id: UUID,
        body: PaymentInput,
        user=Depends(admin),
    ):
        try:
            with connect() as conn:
                order = load_order(conn, order_id, user, lock=True)

                existing = conn.execute(
                    'SELECT * FROM order_payments WHERE order_id=%s',
                    (order_id,),
                ).fetchone()

                if existing:
                    if (
                        existing['method'] != body.method
                        or existing['reference'] != body.reference
                    ):
                        raise HTTPException(
                            409,
                            'Payment already recorded with different details',
                        )
                    return payment_info(existing)

                if order['status'] != 'ready':
                    raise HTTPException(
                        409,
                        'Payment can be recorded only when an order is ready',
                    )

                if order['payment_status'] != 'unpaid':
                    raise HTTPException(
                        409,
                        'This order cannot receive another payment',
                    )

                items = conn.execute(
                    '''
                    SELECT product_name, quantity, unit_price
                    FROM order_items
                    WHERE order_id=%s
                    ORDER BY id
                    ''',
                    (order_id,),
                ).fetchall()

                total = sum(
                    (item['unit_price'] * item['quantity'] for item in items),
                    Decimal('0'),
                )

                if not items or total != order['total']:
                    raise HTTPException(
                        409,
                        'Order total does not match its bill. Review the order',
                    )

                brand = conn.execute(
                    'SELECT name FROM university_brand WHERE id=1'
                ).fetchone()

                snapshot = {
                    'university': brand['name'],
                    'customer_name': order['customer_name'],
                    'order_id': str(order_id),
                    'pickup_name': order['pickup_name'] or 'Campus store',
                    'total': format(total, '.2f'),
                    'items': [
                        {
                            'name': item['product_name'],
                            'quantity': item['quantity'],
                            'unit_price': format(item['unit_price'], '.2f'),
                            'line_total': format(
                                item['unit_price'] * item['quantity'],
                                '.2f',
                            ),
                        }
                        for item in items
                    ],
                }

                payment = conn.execute(
                    '''
                    INSERT INTO order_payments(
                        order_id, amount, method, reference,
                        recorded_by, snapshot
                    )
                    VALUES(%s,%s,%s,%s,%s,%s)
                    RETURNING *
                    ''',
                    (
                        order_id, total, body.method, body.reference,
                        user['id'], Jsonb(snapshot),
                    ),
                ).fetchone()

                conn.execute(
                    "UPDATE orders SET payment_status='paid' WHERE id=%s",
                    (order_id,),
                )

                notify(
                    conn,
                    order['user_id'],
                    'Payment received',
                    'Payment has been recorded. Your receipt is available in My orders.',
                    order_id,
                )

                return payment_info(payment)

        except psycopg.errors.UniqueViolation:
            raise HTTPException(
                409,
                'That UPI transaction reference is already recorded',
            )

    @router.get(
        '/api/orders/{order_id}/receipt',
        response_class=HTMLResponse,
    )
    def receipt(
        order_id: UUID,
        view: bool = False,
        user=Depends(current_user),
    ):
        with connect() as conn:
            load_order(conn, order_id, user)

            payment = conn.execute(
                'SELECT * FROM order_payments WHERE order_id=%s',
                (order_id,),
            ).fetchone()

            if not payment:
                raise HTTPException(
                    409,
                    'No payment receipt exists for this order',
                )

        disposition = 'inline' if view else 'attachment'

        return HTMLResponse(
            render_receipt(payment),
            headers={
                'Content-Disposition': (
                    f'{disposition}; '
                    f'filename="campuscart-receipt-{payment["id"]}.html"'
                ),
                'Cache-Control': 'no-store',
                'Content-Security-Policy': (
                    "default-src 'none'; style-src 'unsafe-inline'"
                ),
            },
        )

    @router.get('/api/admin/billing-summary')
    def summary(user=Depends(admin)):
        with connect() as conn:
            return {
                'received': conn.execute(
                    'SELECT coalesce(sum(amount),0) n FROM order_payments'
                ).fetchone()['n'],
                'paid_orders': conn.execute(
                    'SELECT count(*) n FROM order_payments'
                ).fetchone()['n'],
                'awaiting_payment': conn.execute(
                    '''
                    SELECT coalesce(sum(total),0) n
                    FROM orders
                    WHERE status='ready' AND payment_status='unpaid'
                    '''
                ).fetchone()['n'],
            }

    return router