import React, {useEffect, useState} from 'react';
import {api} from './session';
import {money} from './catalog';
import './billing.css';

export function OrderBilling({order, admin=false, onPaid}) {
  const [open, setOpen] = useState(false);
  const [bill, setBill] = useState(null);
  const [method, setMethod] = useState('cash');
  const [reference, setReference] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function load() {
    setError('');
    try {
      setBill(await api('/orders/'+order.id+'/billing'));
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    if (open) load();
  }, [order.payment_status]);

  async function record(e) {
    e.preventDefault();
    setBusy(true);
    setError('');

    try {
      await api('/admin/orders/'+order.id+'/payment', {
        method: 'POST',
        body: {method, reference, confirmed}
      });

      await load();
      setConfirmed(false);
      await onPaid?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const status =
    bill?.payment_status || order.payment_status || 'unpaid';

  const label = order.status === 'cancelled'
    ? 'No payment due'
    : status === 'legacy_unrecorded'
      ? 'Payment not recorded (legacy)'
      : status === 'paid'
        ? 'Paid'
        : 'Unpaid · pay at pickup';

  return (
    <section className="billing-box">
      <div className="billing-heading">
        <span className={'payment-badge '+status}>{label}</span>
        <button
          className="text-button"
          onClick={() => {
            if (!open) load();
            setOpen(!open);
          }}
        >
          {open ? 'Hide bill' : 'View bill'} →
        </button>
      </div>

      {open && (
        <>
          {error && (
            <p className="form-error" role="alert">{error}</p>
          )}

          {!bill ? (
            <p>Loading bill…</p>
          ) : (
            <>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th>Qty</th>
                      <th>Unit price</th>
                      <th>Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bill.items.map((item, i) => (
                      <tr key={i}>
                        <td>{item.product_name}</td>
                        <td>{item.quantity}</td>
                        <td>{money(item.unit_price)}</td>
                        <td>
                          {money(Number(item.unit_price)*item.quantity)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <p className="bill-total">
                Total <strong>{money(bill.total)}</strong>
              </p>
              <p className="billing-help">
                Saved order prices. No extra tax or fee is added.
                Payment is received at campus pickup.
              </p>

              {bill.payment && (
                <div className="receipt-links">
                  <p>
                    <strong>{bill.payment.receipt_number}</strong>
                    {' · '+bill.payment.method.toUpperCase()}
                    {bill.payment.reference &&
                      ' · '+bill.payment.reference}
                  </p>

                  <a
                    className="button outline"
                    href={'/api/orders/'+order.id+'/receipt'}
                  >
                    Download receipt
                  </a>

                  <a
                    className="text-button"
                    href={'/api/orders/'+order.id+'/receipt?view=true'}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Print / save PDF ↗
                  </a>
                </div>
              )}

              {admin && order.status === 'ready' &&
                status === 'unpaid' && (
                  <form className="payment-form" onSubmit={record}>
                    <h3>Record payment received</h3>

                    <p className="billing-help">
                      Amount due: {money(bill.total)}.
                      This records a payment you have already received;
                      it does not charge the student.
                    </p>

                    <label>
                      Payment method
                      <select
                        value={method}
                        onChange={e => {
                          setMethod(e.target.value);
                          setConfirmed(false);
                        }}
                      >
                        <option value="cash">
                          Cash at collection desk
                        </option>
                        <option value="upi">
                          UPI received at pickup
                        </option>
                      </select>
                    </label>

                    {method === 'upi' && (
                      <label>
                        Verified UPI transaction reference
                        <input
                          value={reference}
                          onChange={e => setReference(e.target.value)}
                          required
                          minLength={3}
                          maxLength={100}
                        />
                      </label>
                    )}

                    <label className="payment-confirm">
                      <input
                        type="checkbox"
                        required
                        checked={confirmed}
                        onChange={e => setConfirmed(e.target.checked)}
                      />
                      {method === 'cash'
                        ? 'I confirm the full cash amount was received.'
                        : 'I verified the full UPI amount in the receiving account.'}
                    </label>

                    <button
                      className="button navy"
                      disabled={busy || !confirmed}
                    >
                      {busy
                        ? 'Recording…'
                        : 'Confirm payment received'}
                    </button>
                  </form>
                )}
            </>
          )}
        </>
      )}
    </section>
  );
}

export function BillingSummary() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');

  async function load() {
    try {
      setData(await api('/admin/billing-summary'));
      setError('');
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="billing-summary">
      <div className="billing-heading">
        <h2>Recorded payments</h2>
        <button className="text-button" onClick={load}>
          Refresh
        </button>
      </div>

      {error && <p className="form-error">{error}</p>}

      {data && (
        <div className="stat-grid">
          {[
            ['Payments received', money(data.received)],
            ['Paid orders', data.paid_orders],
            ['Ready orders awaiting payment',
              money(data.awaiting_payment)]
          ].map(([label, value]) => (
            <div className="stat-card" key={label}>
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>
      )}

      <p className="billing-help">
        All-time payments confirmed by staff, separate from order value.
        Legacy payments are not assumed.
      </p>
    </div>
  );
}