from datetime import datetime,timedelta,time,timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException
LOCAL_ZONE=ZoneInfo('Asia/Kolkata')

def notify(conn,user_id,title,message,order_id=None):
    if user_id:
        conn.execute('INSERT INTO notifications(user_id,title,message,order_id) VALUES(%s,%s,%s,%s)',(user_id,title,message,order_id))

def inventory_alert(conn,product):
    # Call while holding the product row lock. One alert per low-stock episode.
    is_low=bool(product['active'] and product['stock']<=5)
    previous=conn.execute('SELECT is_low FROM inventory_alert_state WHERE product_id=%s',(product['id'],)).fetchone()
    conn.execute('INSERT INTO inventory_alert_state(product_id,is_low) VALUES(%s,%s) ON CONFLICT(product_id) DO UPDATE SET is_low=excluded.is_low',(product['id'],is_low))
    if is_low and (not previous or not previous['is_low']):
        for user in conn.execute("SELECT id FROM users WHERE role='admin'").fetchall():
            notify(conn,user['id'],'Low stock: '+product['name'],f"{product['stock']} units remaining. Review the product inventory.")

def ensure_slots(conn,location_id):
    if not conn.execute('SELECT id FROM pickup_locations WHERE id=%s AND active',(location_id,)).fetchone():
        raise HTTPException(404,'Pickup location not found')
    today=datetime.now(LOCAL_ZONE).date()
    for offset in range(14):
        day=today+timedelta(days=offset)
        if day.weekday()>=5:continue
        for hour in (10,12,14):
            start=datetime.combine(day,time(hour),LOCAL_ZONE)
            if start<=datetime.now(LOCAL_ZONE):continue
            conn.execute('INSERT INTO pickup_slots(location_id,starts_at,ends_at) VALUES(%s,%s,%s) ON CONFLICT(location_id,starts_at) DO NOTHING',(location_id,start,start+timedelta(hours=2)))

def parse_collection_code(code):
    from uuid import UUID
    try:
        prefix,order_id,token=code.strip().split(':')
        if prefix!='CC3' or not 32<=len(token)<=64:raise ValueError()
        return UUID(order_id),token
    except (ValueError,TypeError,AttributeError):
        raise HTTPException(422,'Enter a valid CampusCart collection code')
