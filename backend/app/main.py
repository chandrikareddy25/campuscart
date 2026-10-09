import os
import time
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field, model_validator
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = FastAPI(title="CampusCart API", version="0.1.0")
REQUESTS = Counter("campuscart_http_requests_total", "HTTP requests", ["method", "route", "status"])
LATENCY = Histogram("campuscart_http_request_duration_seconds", "Request latency", ["route"])
ORDERS = Counter("campuscart_orders_created_total", "Orders created")


def connect():
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row, connect_timeout=5)


@app.middleware("http")
async def measure(request: Request, call_next):
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        label = route.path if route else "unmatched"
        if label != "/metrics":
            REQUESTS.labels(request.method, label, str(status)).inc()
            LATENCY.labels(label).observe(time.perf_counter() - started)


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready():
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
        return {"status": "ready"}
    except psycopg.Error:
        raise HTTPException(503, "Database unavailable")


@app.get("/api/products")
def products():
    with connect() as conn:
        return conn.execute("SELECT * FROM products ORDER BY id").fetchall()


class OrderItem(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=100)


class OrderInput(BaseModel):
    customer_name: str = Field(min_length=1, max_length=100)
    items: list[OrderItem] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_items(self):
        self.customer_name = self.customer_name.strip()
        if not self.customer_name:
            raise ValueError("Customer name is required")
        ids = [item.product_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate products are not allowed")
        return self


@app.post("/api/orders", status_code=201)
def create_order(body: OrderInput):
    # Lock products in a consistent order to prevent overselling and deadlocks.
    with connect() as conn:
        lines = []
        total = Decimal("0")
        for item in sorted(body.items, key=lambda item: item.product_id):
            product = conn.execute("SELECT * FROM products WHERE id=%s FOR UPDATE", (item.product_id,)).fetchone()
            if product is None:
                raise HTTPException(404, "Product not found")
            if product["stock"] < item.quantity:
                raise HTTPException(409, f"Insufficient stock for {product['name']}")
            total += product["price"] * item.quantity
            lines.append((product, item.quantity))
        order = conn.execute(
            "INSERT INTO orders(customer_name,total) VALUES (%s,%s) RETURNING id,total,created_at",
            (body.customer_name, total),
        ).fetchone()
        for product, quantity in lines:
            conn.execute("UPDATE products SET stock=stock-%s WHERE id=%s", (quantity, product["id"]))
            conn.execute(
                "INSERT INTO order_items(order_id,product_id,product_name,quantity,unit_price) VALUES (%s,%s,%s,%s,%s)",
                (order["id"], product["id"], product["name"], quantity, product["price"]),
            )
    # The connection context commits only after all changes succeed.
    ORDERS.inc()
    return order
