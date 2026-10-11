import os
import re
import secrets
import time
import hashlib
import json
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from decimal import Decimal
from uuid import UUID
from urllib.parse import urlsplit
from app.billing import create_billing_router, require_paid

import psycopg
from psycopg.types.json import Jsonb
from fastapi import FastAPI, HTTPException, Request, Response, Depends
from pydantic import BaseModel, Field, model_validator
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from app.db import connect, migrate
from app.security import hash_password, verify_password, token_hash
from app.services import notify, inventory_alert, ensure_slots, parse_collection_code

@asynccontextmanager
async def lifespan(app):
    migrate()
    yield

app=FastAPI(title='CampusCart University API',version='3.0.0',lifespan=lifespan)
REQUESTS=Counter('campuscart_http_requests_total','HTTP requests',['method','route','status'])
LATENCY=Histogram('campuscart_http_request_duration_seconds','Request latency',['route'])
ORDERS=Counter('campuscart_orders_created_total','Orders created')
LOGIN_ATTEMPTS=defaultdict(deque)
STATUSES=['placed','preparing','ready','collected']

@app.middleware('http')
async def measure(request, call_next):
    started=time.perf_counter();status=500
    try:
        response=await call_next(request);status=response.status_code
        response.headers['X-Content-Type-Options']='nosniff'
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control']='no-store'
        return response
    finally:
        route=request.scope.get('route');label=route.path if route else 'unmatched'
        if label!='/metrics':
            REQUESTS.labels(request.method,label,str(status)).inc()
            LATENCY.labels(label).observe(time.perf_counter()-started)

@app.get('/metrics',include_in_schema=False)
def metrics():return Response(generate_latest(),headers={'Content-Type':CONTENT_TYPE_LATEST})
@app.get('/health/live')
def live():return {'status':'ok'}
@app.get('/health/ready')
def ready():
    try:
        with connect() as conn:conn.execute('SELECT 1')
        return {'status':'ready'}
    except psycopg.Error:raise HTTPException(503,'Database unavailable')

class Credentials(BaseModel):
    email:str=Field(min_length=3,max_length=254)
    password:str=Field(min_length=12,max_length=128)
    @model_validator(mode='after')
    def clean(self):
        self.email=self.email.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',self.email):raise ValueError('Enter a valid email')
        return self
class Registration(Credentials):
    name:str=Field(min_length=1,max_length=100)
    student_id:str=Field(default='',max_length=50)
    @model_validator(mode='after')
    def clean_name(self):
        self.name=self.name.strip()
        if not self.name:raise ValueError('Name is required')
        return self
class Profile(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    student_id:str=Field(default='',max_length=50)
class PasswordChange(BaseModel):
    current_password:str=Field(max_length=128)
    new_password:str=Field(min_length=12,max_length=128)

def public_user(user):return {k:user[k] for k in ['id','email','name','role','student_id']}
def new_session(conn,user,response):
    token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(24)
    conn.execute("DELETE FROM sessions WHERE expires_at<now()")
    conn.execute("INSERT INTO sessions(token_hash,user_id,csrf_token,expires_at) VALUES(%s,%s,%s,now()+interval '24 hours')",(token_hash(token),user['id'],csrf))
    response.set_cookie('campuscart_session',token,max_age=86400,httponly=True,samesite='strict',secure=os.getenv('COOKIE_SECURE')=='true',path='/')
    return {'user':public_user(user),'csrf':csrf}

def current_user(request:Request):
    token=request.cookies.get('campuscart_session')
    if not token:raise HTTPException(401,'Please sign in')
    with connect() as conn:
        row=conn.execute('SELECT u.*,s.csrf_token FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=%s AND s.expires_at>now()',(token_hash(token),)).fetchone()
    if not row:raise HTTPException(401,'Session expired. Please sign in again')
    if request.method not in ('GET','HEAD','OPTIONS'):
        if not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),row['csrf_token']):raise HTTPException(403,'Invalid request token. Reload and try again')
    return row

def admin(user=Depends(current_user)):
    if user['role']!='admin':raise HTTPException(403,'Administrator access required')
    return user

def limit_login(request,email):
    key=(request.client.host,email);q=LOGIN_ATTEMPTS[key];now=time.monotonic()
    while q and q[0]<now-300:q.popleft()
    if len(q)>=10:raise HTTPException(429,'Too many sign-in attempts. Wait five minutes')
    q.append(now)
    if len(LOGIN_ATTEMPTS)>10000:
        for k in list(LOGIN_ATTEMPTS):
            if not LOGIN_ATTEMPTS[k] or LOGIN_ATTEMPTS[k][-1]<now-300:del LOGIN_ATTEMPTS[k]

@app.post('/api/auth/register',status_code=201)
def register(body:Registration,request:Request,response:Response):
    limit_login(request,body.email)
    try:
        with connect() as conn:
            user=conn.execute("INSERT INTO users(email,name,password_hash,student_id) VALUES(%s,%s,%s,%s) RETURNING *",(body.email,body.name,hash_password(body.password),body.student_id)).fetchone()
            return new_session(conn,user,response)
    except psycopg.errors.UniqueViolation:raise HTTPException(409,'An account already exists for that email')
@app.post('/api/auth/login')
def login(body:Credentials,request:Request,response:Response):
    limit_login(request,body.email)
    with connect() as conn:
        user=conn.execute('SELECT * FROM users WHERE email=%s',(body.email,)).fetchone()
        if not user or not verify_password(body.password,user['password_hash']):raise HTTPException(401,'Invalid email or password')
        return new_session(conn,user,response)
@app.get('/api/auth/me')
def me(user=Depends(current_user)):return {'user':public_user(user),'csrf':user['csrf_token']}
@app.post('/api/auth/logout')
def logout(request:Request,response:Response,user=Depends(current_user)):
    with connect() as conn:conn.execute('DELETE FROM sessions WHERE token_hash=%s',(token_hash(request.cookies['campuscart_session']),))
    response.delete_cookie('campuscart_session',path='/');return {'ok':True}
@app.patch('/api/profile')
def profile(body:Profile,user=Depends(current_user)):
    if not body.name.strip():raise HTTPException(422,'Name is required')
    with connect() as conn:
        row=conn.execute('UPDATE users SET name=%s,student_id=%s WHERE id=%s RETURNING *',(body.name.strip(),body.student_id,user['id'])).fetchone()
    return public_user(row)
@app.post('/api/profile/password')
def password(body:PasswordChange,user=Depends(current_user)):
    if not verify_password(body.current_password,user['password_hash']):raise HTTPException(400,'Current password is incorrect')
    with connect() as conn:
        conn.execute('UPDATE users SET password_hash=%s WHERE id=%s',(hash_password(body.new_password),user['id']))
        conn.execute('DELETE FROM sessions WHERE user_id=%s',(user['id'],))
    return {'ok':True,'message':'Password changed. Sign in again.'}

@app.get('/api/products')
def products():
    with connect() as conn:return conn.execute('SELECT * FROM products WHERE active ORDER BY featured DESC,id').fetchall()
@app.get('/api/products/{product_id}')
def product(product_id:int):
    with connect() as conn:row=conn.execute('SELECT * FROM products WHERE id=%s AND active',(product_id,)).fetchone()
    if not row:raise HTTPException(404,'Product not found')
    return row
@app.get('/api/pickup-locations')
def pickups():
    with connect() as conn:return conn.execute('SELECT * FROM pickup_locations WHERE active ORDER BY id').fetchall()

class CartLine(BaseModel):
    product_id:int=Field(gt=0)
    quantity:int=Field(ge=0,le=100)
@app.get('/api/cart')
def cart(user=Depends(current_user)):
    with connect() as conn:return conn.execute('SELECT p.*,c.quantity FROM carts c JOIN products p ON p.id=c.product_id WHERE c.user_id=%s ORDER BY p.id',(user['id'],)).fetchall()
@app.put('/api/cart')
def update_cart(body:CartLine,user=Depends(current_user)):
    with connect() as conn:
        p=conn.execute('SELECT stock,active FROM products WHERE id=%s',(body.product_id,)).fetchone()
        if not p:raise HTTPException(404,'Product not found')
        if body.quantity and (not p['active'] or body.quantity>p['stock']):raise HTTPException(409,'That quantity is unavailable')
        if body.quantity:conn.execute('INSERT INTO carts(user_id,product_id,quantity) VALUES(%s,%s,%s) ON CONFLICT(user_id,product_id) DO UPDATE SET quantity=excluded.quantity',(user['id'],body.product_id,body.quantity))
        else:conn.execute('DELETE FROM carts WHERE user_id=%s AND product_id=%s',(user['id'],body.product_id))
    return {'ok':True}
@app.get('/api/wishlist')
def wishlist(user=Depends(current_user)):
    with connect() as conn:return conn.execute('SELECT p.* FROM wishlists w JOIN products p ON p.id=w.product_id WHERE w.user_id=%s AND p.active ORDER BY p.id',(user['id'],)).fetchall()
@app.put('/api/wishlist/{product_id}')
def wish(product_id:int,user=Depends(current_user)):
    with connect() as conn:
        if not conn.execute('SELECT 1 FROM products WHERE id=%s AND active',(product_id,)).fetchone():raise HTTPException(404,'Product not found')
        conn.execute('INSERT INTO wishlists(user_id,product_id) VALUES(%s,%s) ON CONFLICT DO NOTHING',(user['id'],product_id))
    return {'ok':True}
@app.delete('/api/wishlist/{product_id}')
def unwish(product_id:int,user=Depends(current_user)):
    with connect() as conn:conn.execute('DELETE FROM wishlists WHERE user_id=%s AND product_id=%s',(user['id'],product_id))
    return {'ok':True}

class Address(BaseModel):
    label:str=Field(min_length=1,max_length=50)
    address:str=Field(min_length=1,max_length=500)
@app.get('/api/addresses')
def addresses(user=Depends(current_user)):
    with connect() as conn:return conn.execute('SELECT * FROM addresses WHERE user_id=%s ORDER BY id',(user['id'],)).fetchall()
@app.post('/api/addresses',status_code=201)
def add_address(body:Address,user=Depends(current_user)):
    with connect() as conn:
        if conn.execute('SELECT count(*) n FROM addresses WHERE user_id=%s',(user['id'],)).fetchone()['n']>=10:raise HTTPException(409,'Maximum ten saved addresses')
        return conn.execute('INSERT INTO addresses(user_id,label,address) VALUES(%s,%s,%s) RETURNING *',(user['id'],body.label,body.address)).fetchone()
@app.delete('/api/addresses/{address_id}')
def delete_address(address_id:int,user=Depends(current_user)):
    with connect() as conn:conn.execute('DELETE FROM addresses WHERE id=%s AND user_id=%s',(address_id,user['id']))
    return {'ok':True}

class OrderItem(BaseModel):
    product_id:int=Field(gt=0)
    quantity:int=Field(gt=0,le=100)
class OrderInput(BaseModel):
    customer_name:str=Field(min_length=1,max_length=100)
    items:list[OrderItem]=Field(min_length=1,max_length=30)
    pickup_location_id:int|None=Field(default=None,gt=0)
    pickup_slot_id:int|None=Field(default=None,gt=0)
    notes:str=Field(default='',max_length=500)
    request_key:UUID|None=None
    @model_validator(mode='after')
    def validate_items(self):
        self.customer_name=self.customer_name.strip()
        if not self.customer_name:raise ValueError('Name is required')
        ids=[i.product_id for i in self.items]
        if len(ids)!=len(set(ids)):raise ValueError('Duplicate products are not allowed')
        return self

def order_detail(conn,order):
    order.pop('collection_token',None)
    if order.get('pickup_slot_id'):
        order['pickup_slot']=conn.execute('SELECT starts_at,ends_at FROM pickup_slots WHERE id=%s',(order['pickup_slot_id'],)).fetchone()
    order['items']=conn.execute('SELECT * FROM order_items WHERE order_id=%s ORDER BY id',(order['id'],)).fetchall()
    order['events']=conn.execute('SELECT status,created_at FROM order_events WHERE order_id=%s ORDER BY id',(order['id'],)).fetchall()
    return order
@app.post('/api/orders',status_code=201)
def create_order(body:OrderInput,user=Depends(current_user)):
    # RELEASE EXPERIMENT FAULT
    raise HTTPException(500, 'Controlled release experiment')
    if not body.pickup_location_id or not body.pickup_slot_id or not body.request_key:raise HTTPException(422,'Choose a pickup location, time slot, and provide a request key')
    with connect() as conn:
        # Serializes same-user checkout, including duplicate request keys.
        conn.execute('SELECT id FROM users WHERE id=%s FOR UPDATE',(user['id'],))
        existing=conn.execute('SELECT * FROM orders WHERE user_id=%s AND request_key=%s',(user['id'],body.request_key)).fetchone()
        if existing:return order_detail(conn,existing)
        pickup=conn.execute('SELECT * FROM pickup_locations WHERE id=%s AND active',(body.pickup_location_id,)).fetchone()
        if not pickup:raise HTTPException(422,'Pickup location unavailable')
        slot=conn.execute('SELECT * FROM pickup_slots WHERE id=%s AND location_id=%s FOR UPDATE',(body.pickup_slot_id,body.pickup_location_id)).fetchone()
        if not slot:raise HTTPException(422,'Choose a valid pickup slot for this location')
        from datetime import datetime,timezone
        if slot['starts_at']<=datetime.now(timezone.utc):raise HTTPException(409,'This pickup slot has already started. Choose another')
        if slot['booked']>=slot['capacity']:raise HTTPException(409,'This pickup slot is full. Choose another')

        lines=[];total=Decimal('0')
        for item in sorted(body.items,key=lambda i:i.product_id):
            p=conn.execute('SELECT * FROM products WHERE id=%s FOR UPDATE',(item.product_id,)).fetchone()
            if not p or not p['active']:raise HTTPException(404,'Product unavailable')
            if p['stock']<item.quantity:raise HTTPException(409,f"Insufficient stock for {p['name']}")
            lines.append((p,item.quantity));total+=p['price']*item.quantity
        order=conn.execute("INSERT INTO orders(customer_name,total,user_id,pickup_location_id,pickup_name,notes,request_key,pickup_slot_id,collection_token) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",(user['name'],total,user['id'],pickup['id'],pickup['name'],body.notes,body.request_key,slot['id'],secrets.token_urlsafe(32))).fetchone()
        conn.execute('UPDATE pickup_slots SET booked=booked+1 WHERE id=%s',(slot['id'],))
        for p,q in lines:
            updated=conn.execute('UPDATE products SET stock=stock-%s WHERE id=%s RETURNING *',(q,p['id'])).fetchone()
            inventory_alert(conn,updated)
            conn.execute('INSERT INTO order_items(order_id,product_id,product_name,quantity,unit_price) VALUES(%s,%s,%s,%s,%s)',(order['id'],p['id'],p['name'],q,p['price']))
            conn.execute('DELETE FROM carts WHERE user_id=%s AND product_id=%s',(user['id'],p['id']))
        conn.execute("INSERT INTO order_events(order_id,status) VALUES(%s,'placed')",(order['id'],))
        notify(conn,user['id'],'Order placed','Your order is confirmed. Track preparation and collection from My orders.',order['id'])
        result=order_detail(conn,order)
    ORDERS.inc();return result
@app.get('/api/orders')
def my_orders(user=Depends(current_user)):
    with connect() as conn:
        return [order_detail(conn,o) for o in conn.execute('SELECT * FROM orders WHERE user_id=%s ORDER BY created_at DESC LIMIT 200',(user['id'],)).fetchall()]
@app.get('/api/orders/{order_id}')
def get_order(order_id:UUID,user=Depends(current_user)):
    with connect() as conn:
        row=conn.execute('SELECT * FROM orders WHERE id=%s AND user_id=%s',(order_id,user['id'])).fetchone()
        if not row:raise HTTPException(404,'Order not found')
        return order_detail(conn,row)

CATEGORIES=['Books','Stationery','Bags','Accessories','Tech','Merchandise','Lab essentials']
class ProductInput(BaseModel):
    name:str=Field(min_length=1,max_length=150)
    description:str=Field(min_length=1,max_length=2000)
    price:Decimal=Field(ge=0,le=99999999,max_digits=10,decimal_places=2)
    stock:int=Field(ge=0,le=100000)
    category:str
    images:list[str]=Field(default_factory=list,max_length=8)
    specifications:dict[str,str]=Field(default_factory=dict)
    active:bool=True
    featured:bool=False
    @model_validator(mode='after')
    def validate_product(self):
        if self.category not in CATEGORIES:raise ValueError('Invalid category')
        if not self.name.strip() or not self.description.strip():raise ValueError('Name and description are required')
        for image in self.images:
            u=urlsplit(image)
            if len(image)>2000 or u.scheme!='https' or not u.netloc or u.username or u.password:raise ValueError('Images must be HTTPS URLs')
        if len(self.specifications)>20 or any(len(k)>100 or len(v)>500 for k,v in self.specifications.items()):raise ValueError('Specifications too long')
        return self
@app.get('/api/admin/products')
def admin_products(user=Depends(admin)):
    with connect() as conn:return conn.execute('SELECT * FROM products ORDER BY id').fetchall()
@app.post('/api/admin/products',status_code=201)
def add_product(body:ProductInput,user=Depends(admin)):
    with connect() as conn:
        row=conn.execute('INSERT INTO products(name,description,price,stock,category,images,specifications,active,featured) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *',(body.name,body.description,body.price,body.stock,body.category,Jsonb(body.images),Jsonb(body.specifications),body.active,body.featured)).fetchone()
        inventory_alert(conn,row)
    return row
@app.put('/api/admin/products/{product_id}')
def edit_product(product_id:int,body:ProductInput,user=Depends(admin)):
    with connect() as conn:
        row=conn.execute('UPDATE products SET name=%s,description=%s,price=%s,stock=%s,category=%s,images=%s,specifications=%s,active=%s,featured=%s WHERE id=%s RETURNING *',(body.name,body.description,body.price,body.stock,body.category,Jsonb(body.images),Jsonb(body.specifications),body.active,body.featured,product_id)).fetchone()
        if not row:raise HTTPException(404,'Product not found')
        inventory_alert(conn,row)
    return row
@app.get('/api/admin/orders')
def admin_orders(user=Depends(admin)):
    with connect() as conn:return [order_detail(conn,o) for o in conn.execute('SELECT * FROM orders ORDER BY created_at DESC LIMIT 500').fetchall()]
class StatusChange(BaseModel):status:str
@app.patch('/api/admin/orders/{order_id}/status')
def change_status(order_id:UUID,body:StatusChange,user=Depends(admin)):
    with connect() as conn:
        order=conn.execute('SELECT * FROM orders WHERE id=%s FOR UPDATE',(order_id,)).fetchone()
        if not order:raise HTTPException(404,'Order not found')
        if body.status not in STATUSES:raise HTTPException(422,'Unknown status')
        if order['status']=='cancelled':raise HTTPException(409,'Cancelled orders cannot be advanced')
        if body.status == order['status']:
            order.pop('collection_token', None)
            return order

        if body.status == 'collected':
            require_paid(order)

        if body.status == 'collected' and order['collection_token']:
            raise HTTPException(
                409,
                'Use the collection desk to verify the QR code'
            )
        if STATUSES.index(body.status)!=STATUSES.index(order['status'])+1:raise HTTPException(409,'Orders must advance one stage at a time')
        row=conn.execute('UPDATE orders SET status=%s WHERE id=%s RETURNING *',(body.status,order_id)).fetchone()
        conn.execute('INSERT INTO order_events(order_id,status) VALUES(%s,%s)',(order_id,body.status))
        notify(conn,order['user_id'],'Ready for collection' if body.status=='ready' else 'Order '+body.status,'Your campus order is '+body.status+'. Open My orders for collection details.',order_id)
        row.pop('collection_token',None)
    return row
@app.get('/api/admin/analytics')
def analytics(user=Depends(admin)):
    with connect() as conn:
        return {
          'summary':conn.execute("SELECT count(*) orders,coalesce(sum(total) FILTER(WHERE status<>'cancelled'),0) revenue,count(*) FILTER(WHERE status='placed') new_orders,count(*) FILTER(WHERE status='ready') ready_orders FROM orders").fetchone(),
          'products':conn.execute('SELECT count(*) total,count(*) FILTER(WHERE stock<=5 AND active) low_stock FROM products').fetchone(),
          'students':conn.execute("SELECT count(*) count FROM users WHERE role='student'").fetchone()['count'],
          'daily':conn.execute("SELECT d::date AS \"day\",count(o.id) orders,coalesce(sum(o.total),0) revenue FROM generate_series(current_date-13,current_date,interval '1 day') d LEFT JOIN orders o ON o.created_at::date=d::date AND o.status<>'cancelled' GROUP BY d ORDER BY d").fetchall(),
          'categories':conn.execute("SELECT p.category,sum(i.quantity) units,sum(i.quantity*i.unit_price) revenue FROM order_items i JOIN products p ON p.id=i.product_id JOIN orders o ON o.id=i.order_id WHERE o.status<>'cancelled' GROUP BY p.category ORDER BY revenue DESC").fetchall(),
          'low_stock':conn.execute('SELECT id,name,stock FROM products WHERE active AND stock<=5 ORDER BY stock,id LIMIT 20').fetchall()
        }

@app.get('/api/brand')
def brand():
    with connect() as conn:return conn.execute('SELECT name,initials,tagline FROM university_brand WHERE id=1').fetchone()
class BrandInput(BaseModel):
    name:str=Field(min_length=3,max_length=80)
    initials:str=Field(min_length=1,max_length=5)
    tagline:str=Field(min_length=3,max_length=140)
    @model_validator(mode='after')
    def clean(self):
        self.name=self.name.strip();self.initials=self.initials.strip().upper();self.tagline=self.tagline.strip()
        if not self.name or not self.initials or not self.tagline:raise ValueError('Brand fields cannot be empty')
        return self
@app.put('/api/admin/brand')
def update_brand(body:BrandInput,user=Depends(admin)):
    with connect() as conn:return conn.execute('UPDATE university_brand SET name=%s,initials=%s,tagline=%s WHERE id=1 RETURNING name,initials,tagline',(body.name,body.initials,body.tagline)).fetchone()

@app.get('/api/pickup-slots')
def pickup_slots(location_id:int):
    with connect() as conn:
        ensure_slots(conn,location_id)
        return conn.execute('SELECT id,location_id,starts_at,ends_at,capacity,booked,capacity-booked remaining FROM pickup_slots WHERE location_id=%s AND starts_at>now() ORDER BY starts_at',(location_id,)).fetchall()
class SlotCapacity(BaseModel):capacity:int=Field(ge=1,le=500)
@app.patch('/api/admin/pickup-slots/{slot_id}')
def update_capacity(slot_id:int,body:SlotCapacity,user=Depends(admin)):
    with connect() as conn:
        row=conn.execute('SELECT * FROM pickup_slots WHERE id=%s FOR UPDATE',(slot_id,)).fetchone()
        if not row:raise HTTPException(404,'Pickup slot not found')
        if body.capacity<row['booked']:raise HTTPException(409,'Capacity cannot be below existing reservations')
        conn.execute('UPDATE pickup_slots SET capacity=%s WHERE id=%s',(body.capacity,slot_id))
    return {'ok':True}

@app.post('/api/orders/{order_id}/cancel')
def cancel_order(order_id:UUID,user=Depends(current_user)):
    with connect() as conn:
        order=conn.execute('SELECT * FROM orders WHERE id=%s AND user_id=%s FOR UPDATE',(order_id,user['id'])).fetchone()
        if not order:raise HTTPException(404,'Order not found')
        if order['status']=='cancelled':return {'ok':True,'status':'cancelled'}
        if order['payment_status'] == 'paid':
            raise HTTPException(409, 'Paid orders cannot be cancelled')
        if order['status']!='placed':raise HTTPException(409,'This order is already being prepared and cannot be cancelled')
        # Lock slots before products, matching checkout's lock order.
        if order['pickup_slot_id']:
            conn.execute('UPDATE pickup_slots SET booked=booked-1 WHERE id=%s',(order['pickup_slot_id'],))
        for item in conn.execute('SELECT product_id,quantity FROM order_items WHERE order_id=%s ORDER BY product_id',(order_id,)).fetchall():
            updated=conn.execute('UPDATE products SET stock=stock+%s WHERE id=%s RETURNING *',(item['quantity'],item['product_id'])).fetchone()
            inventory_alert(conn,updated)
        conn.execute("UPDATE orders SET status='cancelled',collection_token=NULL WHERE id=%s",(order_id,))
        conn.execute("INSERT INTO order_events(order_id,status) VALUES(%s,'cancelled')",(order_id,))
        notify(conn,user['id'],'Order cancelled','Your items were returned to stock and your pickup reservation released.',order_id)
    return {'ok':True,'status':'cancelled'}
@app.get('/api/orders/{order_id}/collection')
def collection_code(order_id:UUID,user=Depends(current_user)):
    with connect() as conn:
        row=conn.execute('SELECT status,collection_token FROM orders WHERE id=%s AND user_id=%s',(order_id,user['id'])).fetchone()
        if not row:raise HTTPException(404,'Order not found')
        if row['status']!='ready':raise HTTPException(409,'Collection code becomes available when the order is ready')
        if not row['collection_token']:raise HTTPException(409,'This legacy order uses manual collection')
        return {'code':f"CC3:{order_id}:{row['collection_token']}"}
class CollectionInput(BaseModel):code:str=Field(min_length=10,max_length=200)
@app.post('/api/admin/collect')
def collect_order(body: CollectionInput, user=Depends(admin)):
    order_id, token = parse_collection_code(body.code)

    with connect() as conn:
        order = conn.execute(
            'SELECT * FROM orders WHERE id=%s FOR UPDATE',
            (order_id,),
        ).fetchone()

        if (
            not order
            or not order['collection_token']
            or not secrets.compare_digest(order['collection_token'], token)
        ):
            raise HTTPException(404, 'Collection code is invalid')

        if order['status'] == 'collected':
            raise HTTPException(409, 'This order has already been collected')

        if order['status'] != 'ready':
            raise HTTPException(409, 'Only ready orders can be collected')

        require_paid(order)

        conn.execute(
            "UPDATE orders SET status='collected' WHERE id=%s",
            (order_id,),
        )
        conn.execute(
            "INSERT INTO order_events(order_id,status) VALUES(%s,'collected')",
            (order_id,),
        )
        notify(
            conn,
            order['user_id'],
            'Order collected',
            'Your campus collection is complete. Thank you for shopping with us.',
            order_id,
        )

        return {
            'ok': True,
            'order_id': order_id,
            'customer_name': order['customer_name'],
        }

@app.get('/api/notifications')
def notifications(user=Depends(current_user)):
    with connect() as conn:
        return {'items':conn.execute('SELECT * FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT 100',(user['id'],)).fetchall(),
                'unread':conn.execute('SELECT count(*) n FROM notifications WHERE user_id=%s AND read_at IS NULL',(user['id'],)).fetchone()['n']}
@app.post('/api/notifications/read-all')
def read_all_notifications(user=Depends(current_user)):
    with connect() as conn:conn.execute('UPDATE notifications SET read_at=now() WHERE user_id=%s AND read_at IS NULL',(user['id'],))
    return {'ok':True}
@app.patch('/api/notifications/{notification_id}/read')
def read_notification(notification_id:int,user=Depends(current_user)):
    with connect() as conn:conn.execute('UPDATE notifications SET read_at=coalesce(read_at,now()) WHERE id=%s AND user_id=%s',(notification_id,user['id']))
    return {'ok':True}

app.include_router(create_billing_router(current_user, admin))