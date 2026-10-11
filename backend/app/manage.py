import argparse
import getpass
from app.db import connect, migrate
from app.security import hash_password


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['create-admin','migrate'])
    parser.add_argument('--email')
    args=parser.parse_args()
    migrate()
    if args.command=='migrate':
        print('Migrations applied successfully.')
        return
    email=(args.email or input('Admin email: ')).strip().lower()
    if '@' not in email:
        raise SystemExit('Enter a valid email.')
    password=getpass.getpass('Admin password (at least 12 characters): ')
    if len(password)<12 or len(password)>128:
        raise SystemExit('Password must be 12–128 characters.')
    if password!=getpass.getpass('Confirm password: '):
        raise SystemExit('Passwords do not match.')
    with connect() as conn:
        if conn.execute('SELECT 1 FROM users WHERE email=%s',(email,)).fetchone():
            raise SystemExit('That email already exists. No account was changed.')
        conn.execute("INSERT INTO users(email,name,password_hash,role) VALUES(%s,%s,%s,'admin')",(email,'Campus Administrator',hash_password(password)))
    print('Administrator created. Sign in through the storefront.')

if __name__=='__main__':
    main()
