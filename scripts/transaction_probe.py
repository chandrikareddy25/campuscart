"""Executed inside the backend pod; exercises HTTP through frontend service."""
import http.cookiejar
import json
import sys
import time
import uuid
from decimal import Decimal
from urllib.request import Request, build_opener, HTTPCookieProcessor
from urllib.error import HTTPError
from app.db import connect

EMAIL='release-test@campuscart.local'
BASE='http://frontend'
class ProbeFailure(Exception):
    def __init__(self,message,kind='integrity',**details):
        super().__init__(message);self.kind=kind;self.details=details

def dependency_ready():
    try:
        with build_opener().open('http://backend:8000/health/ready',timeout=5) as response:
            return json.load(response).get('status')=='ready'
    except Exception:
        return False

def checkout_constraint():
    # Independent database observation; a conflict alone is not enough.
    try:
        with connect() as c:
            p=c.execute("SELECT stock,active FROM products WHERE specifications->>'release_probe'='true'").fetchall()
            if len(p)!=1:return None
            if not p[0]['active'] or p[0]['stock']<1:return True
            slots=c.execute("SELECT s.capacity,s.booked FROM pickup_slots s JOIN pickup_locations l ON l.id=s.location_id WHERE l.name='Release verification desk' AND s.starts_at>now()").fetchall()
            return bool(slots) and all(x['booked']>=x['capacity'] for x in slots)
    except Exception:
        return None

def require(condition,message):
    if not condition: raise ProbeFailure(message)

# Preserve full existing business rows, rather than comparing only counts/totals.
# Run experiments without concurrent shopping/admin operations.
def snapshot():
    with connect() as c:
        result={}
        for name,sql in {
            'orders':"SELECT o.* FROM orders o LEFT JOIN users u ON u.id=o.user_id WHERE u.email IS DISTINCT FROM %s ORDER BY o.id",
            'order_items':"SELECT i.* FROM order_items i JOIN orders o ON o.id=i.order_id LEFT JOIN users u ON u.id=o.user_id WHERE u.email IS DISTINCT FROM %s ORDER BY i.id",
            'payments':"SELECT p.* FROM order_payments p JOIN orders o ON o.id=p.order_id LEFT JOIN users u ON u.id=o.user_id WHERE u.email IS DISTINCT FROM %s ORDER BY p.id",
            'inventory':"SELECT id,stock FROM products WHERE specifications->>'release_probe' IS DISTINCT FROM 'true' AND %s::text IS NOT NULL ORDER BY id",
        }.items():
            import hashlib
            result[name]=hashlib.sha256(json.dumps(c.execute(sql,(EMAIL,)).fetchall(),default=str,sort_keys=True).encode()).hexdigest()
        return result

def run(password):
    client=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
    csrf=''
    def api(path,method='GET',body=None):
        headers={'Content-Type':'application/json','X-CSRF-Token':csrf}
        req=Request(BASE+path,data=None if body is None else json.dumps(body).encode(),headers=headers,method=method)
        try:
            with client.open(req,timeout=20) as response:
                return json.load(response)
        except HTTPError as e:
            # Do not print response bodies or credentials.
            raise ProbeFailure(f'{method} {path}: HTTP {e.code}',kind='http',http_status=e.code,route=path,dependency_ready=dependency_ready(),constraint_confirmed=checkout_constraint() if e.code==409 and path=='/api/orders' else None) from None
    key=str(uuid.uuid4())
    checks=[]
    observations=[]
    order_id=None
    before=snapshot()
    product_id=slot_id=None
    negative_case=None
    try:
        auth=api('/api/auth/login','POST',{'email':EMAIL,'password':password})
        csrf=auth['csrf'];require(auth['user']['role']=='student','Probe must be a student')
        checks.append('login')
        with connect() as c:
            rows=c.execute("SELECT * FROM products WHERE specifications->>'release_probe'='true'").fetchall()
            require(len(rows)==1,'Prepare exactly one dedicated probe product')
            product=rows[0];product_id=product['id'];stock=product['stock']
            if not (stock>5 and product['active']):
                observations.append({'classification':'business_constraint','stock':stock,'active':product['active']})
                if stock==0 and product['active']:negative_case={'product_id':product_id}
                controls=c.execute("SELECT * FROM products WHERE specifications->>'release_control'='true' AND active AND stock>5").fetchall()
                if len(controls)!=1:raise ProbeFailure('Valid control inventory unavailable',kind='business_precondition')
                product=controls[0];product_id=product['id'];stock=product['stock']
            require(not c.execute("SELECT 1 FROM orders o JOIN users u ON u.id=o.user_id WHERE u.email=%s AND o.status<>'cancelled'",(EMAIL,)).fetchone(),'An earlier test order requires inspection')
        products=api('/api/products');require(any(p['id']==product_id for p in products),'Probe product missing from catalog')
        checks.append('catalog')
        locations=api('/api/pickup-locations')
        location=next((p for p in locations if p['name']=='Release verification desk'),None)
        require(location is not None,'Dedicated pickup desk missing')
        slots=api('/api/pickup-slots?location_id='+str(location['id']))
        slot=next((s for s in slots if s['remaining']>0),None)
        if slot is None:
            observations.append({'classification':'business_constraint','constraint':'pickup_capacity'})
            if slots:negative_case={'slot_id':slots[0]['id'],'location_id':location['id']}
            control_location=next((p for p in locations if p['name']=='Release verification control desk'),None)
            if control_location is None:raise ProbeFailure('Valid control pickup unavailable',kind='business_precondition')
            control_slots=api('/api/pickup-slots?location_id='+str(control_location['id']))
            slot=next((s for s in control_slots if s['remaining']>0),None)
            if slot is None:raise ProbeFailure('No available control test slot',kind='business_precondition')
            location=control_location
        slot_id=slot['id'];booked=slot['booked']
        body={'customer_name':'Release Verification','items':[{'product_id':product_id,'quantity':1}], 'pickup_location_id':location['id'],'pickup_slot_id':slot_id,'request_key':key,'notes':'Automated release verification; no payment collected'}
        if negative_case:
            rejected_body=dict(body)
            if 'product_id' in negative_case:rejected_body['items']=[{'product_id':negative_case['product_id'],'quantity':1}]
            else:
                rejected_body['pickup_slot_id']=negative_case['slot_id'];rejected_body['pickup_location_id']=negative_case['location_id']
            try:
                api('/api/orders','POST',rejected_body)
            except ProbeFailure as e:
                if e.kind!='http' or e.details.get('http_status')!=409:raise
                observations.append({'classification':'expected_business_rejection','http_status':409})
            else:raise ProbeFailure('Business-invalid checkout was accepted')
            # A rejected request must leave neither an order nor a reservation.
            with connect() as c:
                require(not c.execute('SELECT 1 FROM orders o JOIN users u ON u.id=o.user_id WHERE u.email=%s AND o.request_key=%s',(EMAIL,key)).fetchone(),'Rejected checkout created an order')
            checks.append('expected_business_rejection')
        order=api('/api/orders','POST',body);order_id=str(order['id'])
        require(Decimal(str(order['total']))==product['price'],'Incorrect server-calculated order total')
        require(order['status']=='placed','Order not placed')
        checks.append('checkout')
        again=api('/api/orders','POST',body)
        require(str(again['id'])==order_id,'Idempotency returned a different order')
        with connect() as c:
            require(c.execute('SELECT stock FROM products WHERE id=%s',(product_id,)).fetchone()['stock']==stock-1,'Stock must decrement exactly once')
            require(c.execute('SELECT booked FROM pickup_slots WHERE id=%s',(slot_id,)).fetchone()['booked']==booked+1,'Slot must reserve exactly once')
        checks.append('idempotency_and_reservation')
        bill=api('/api/orders/'+order_id+'/billing')
        require(bill['payment_status']=='unpaid' and bill['payment'] is None,'Test order unexpectedly has a payment')
        require(Decimal(str(bill['total']))==product['price'],'Bill total mismatch')
        checks.append('unpaid_billing')
        api('/api/orders/'+order_id+'/cancel','POST',{})
        api('/api/orders/'+order_id+'/cancel','POST',{})
        with connect() as c:
            require(c.execute('SELECT stock FROM products WHERE id=%s',(product_id,)).fetchone()['stock']==stock,'Cancellation did not restore stock exactly once')
            require(c.execute('SELECT booked FROM pickup_slots WHERE id=%s',(slot_id,)).fetchone()['booked']==booked,'Cancellation did not restore slot exactly once')
        checks.append('cancellation_and_restoration')
    finally:
        # A POST response can be lost after committing. Find its order by request key.
        with connect() as c:
            row=c.execute('SELECT o.id,o.status FROM orders o JOIN users u ON u.id=o.user_id WHERE u.email=%s AND o.request_key=%s',(EMAIL,key)).fetchone()
        if row and row['status']=='placed':
            api('/api/orders/'+str(row['id'])+'/cancel','POST',{})
    after=snapshot()
    require(before==after,'Existing business records changed during the probe')
    checks.append('business_data_unchanged')
    return {'checks':checks,'order_id':order_id,'before':before,'after':after,'observations':observations}

if __name__=='__main__':
    started=time.monotonic()
    try:
        result=run(json.load(sys.stdin)['password'])
        result['status']='passed'
    except ProbeFailure as e:
        result={'status':'failed','reason':str(e),'kind':e.kind,**e.details}
    except Exception as e:
        result={'status':'inconclusive','reason':type(e).__name__,'kind':'observation_error'}
    if result['status']!='passed':
        try:
            with connect() as c:
                pending=c.execute("SELECT 1 FROM orders o JOIN users u ON u.id=o.user_id WHERE u.email=%s AND o.status<>'cancelled'",(EMAIL,)).fetchone()
                if pending:result['cleanup_failed']=True
        except Exception:
            result['cleanup_failed']=True
    result['duration_seconds']=round(time.monotonic()-started,3)
    print(json.dumps(result))
    sys.exit(0 if result['status']=='passed' else 1)
