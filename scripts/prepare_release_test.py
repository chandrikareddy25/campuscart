"""Run on WSL once. Password travels through stdin, never command arguments."""
import getpass
import json
import subprocess

CODE = r'''
import json, sys
from app.db import connect
from app.security import hash_password
from psycopg.types.json import Jsonb
body=json.load(sys.stdin)
with connect() as c:
    c.execute('SELECT pg_advisory_xact_lock(892315)')
    u=c.execute('SELECT * FROM users WHERE email=%s',(body['email'],)).fetchone()
    if u and (u['name']!='Release Verification' or u['role']!='student'):
        raise SystemExit('Existing unrelated account: no changes made')
    if not u:
        c.execute("INSERT INTO users(email,name,password_hash,role) VALUES(%s,'Release Verification',%s,'student')",(body['email'],hash_password(body['password'])))
    else:
        c.execute('UPDATE users SET password_hash=%s WHERE id=%s',(hash_password(body['password']),u['id']))
    p=c.execute("SELECT id FROM products WHERE specifications->>'release_probe'='true'").fetchall()
    if len(p)>1: raise SystemExit('More than one probe product exists')
    if not p:
        c.execute("INSERT INTO products(name,description,price,stock,category,specifications) VALUES('Release verification test item','Reserved for pipeline experiments. Do not purchase.',1.00,100,'Stationery',%s)",(Jsonb({'release_probe':True}),))
    c.execute("INSERT INTO pickup_locations(name,instructions) VALUES('Release verification desk','Reserved for automated experiments') ON CONFLICT(name) DO NOTHING")
print('Dedicated test account, product and pickup location prepared.')
'''
if __name__ == '__main__':
    password=getpass.getpass('Test account password (12–128 characters): ')
    if not 12<=len(password)<=128: raise SystemExit('Password must be 12–128 characters')
    if password!=getpass.getpass('Confirm password: '): raise SystemExit('Passwords differ')
    subprocess.run(['kubectl','--context','kind-campuscart','-n','campuscart','exec','-i','deployment/backend','--','python','-c',CODE],input=json.dumps({'email':'release-test@campuscart.local','password':password}),text=True,check=True)
    print('Save this password as the GitHub Actions secret RELEASE_TEST_PASSWORD.')
