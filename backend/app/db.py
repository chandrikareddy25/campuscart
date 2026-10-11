import os
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def connect():
    return psycopg.connect(os.environ['DATABASE_URL'], row_factory=dict_row, connect_timeout=5)


def migrate_v2():
    with connect() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(892314)')
        conn.execute('CREATE TABLE IF NOT EXISTS campuscart_migrations(version INTEGER PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())')
        if conn.execute('SELECT 1 FROM campuscart_migrations WHERE version=2').fetchone():
            return
        conn.execute((Path(__file__).parent/'migrations/002_university.sql').read_text())
        seed = [
            ('Classic Notebook','Space for your next big idea. 200 ruled pages.',80,50,'Stationery'),
            ('Everyday Pen Set','Five smooth blue pens for busy semesters.',60,100,'Stationery'),
            ('Campus Backpack','Lightweight, durable, and ready for class.',899,20,'Bags'),
            ('Database Systems','A practical introduction to relational databases.',550,15,'Books'),
            ('Study Planner','A weekly planner for a focused semester.',199,30,'Stationery'),
            ('Steel Water Bottle','Reusable steel bottle for long campus days.',399,25,'Accessories'),
            ('Wireless Headphones','Over-ear headphones for focused study sessions.',1799,18,'Tech'),
            ('USB-C Hub','A compact hub with USB, HDMI and card-reader ports.',1299,22,'Tech'),
            ('Campus Hoodie','A relaxed university-style cotton blend hoodie.',1199,35,'Merchandise'),
            ('University Tote','An everyday canvas tote for books and essentials.',349,45,'Bags'),
            ('Lab Coat','A practical white coat for supervised laboratory sessions.',649,20,'Lab essentials'),
            ('Safety Goggles','Protective goggles for teaching laboratories.',249,28,'Lab essentials'),
            ('Scientific Calculator','A scientific calculator for everyday coursework.',899,25,'Tech'),
            ('Algorithms Handbook','A companion to data structures and algorithms.',699,18,'Books'),
            ('Campus Mug','A ceramic mug for your desk or common room.',299,40,'Merchandise'),
            ('Desk Organizer','Keep your study space clear and organized.',449,20,'Accessories'),
            ('Laptop Sleeve','A padded sleeve for a 14-inch laptop.',799,24,'Bags'),
            ('Highlighter Set','Six pastel highlighters for your study notes.',149,60,'Stationery'),
        ]
        for name,description,price,stock,category in seed:
            conn.execute('INSERT INTO products(name,description,price,stock,category,specifications,featured) SELECT %s,%s,%s,%s,%s,%s,%s WHERE NOT EXISTS(SELECT 1 FROM products WHERE name=%s)',(name,description,price,stock,category,Jsonb({'Collection':'Campus essentials','Category':category,'Currency':'INR'}),category in ('Tech','Merchandise'),name))
        conn.execute('INSERT INTO campuscart_migrations(version) VALUES (2)')


def migrate():
    migrate_v2()
    with connect() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(892314)')

        for version, filename in (
            (3, '003_campus_services.sql'),
            (4, '004_billing.sql'),
        ):
            applied = conn.execute(
                'SELECT 1 FROM campuscart_migrations WHERE version=%s',
                (version,),
            ).fetchone()

            if not applied:
                conn.execute(
                    (Path(__file__).parent / 'migrations' / filename).read_text()
                )
                conn.execute(
                    'INSERT INTO campuscart_migrations(version) VALUES(%s)',
                    (version,),
                )