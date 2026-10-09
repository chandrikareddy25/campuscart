CREATE TABLE products (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  price NUMERIC(10,2) NOT NULL CHECK(price >= 0),
  stock INTEGER NOT NULL CHECK(stock >= 0)
);
CREATE TABLE orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_name TEXT NOT NULL,
  total NUMERIC(12,2) NOT NULL CHECK(total >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE order_items (
  id SERIAL PRIMARY KEY,
  order_id UUID NOT NULL REFERENCES orders(id),
  product_id INTEGER NOT NULL REFERENCES products(id),
  product_name TEXT NOT NULL,
  quantity INTEGER NOT NULL CHECK(quantity > 0),
  unit_price NUMERIC(10,2) NOT NULL CHECK(unit_price >= 0),
  UNIQUE(order_id,product_id)
);
INSERT INTO products(name,description,price,stock) VALUES
('Classic Notebook','Space for your next big idea. 200 ruled pages.',80,50),
('Everyday Pen Set','Five smooth blue pens for busy semesters.',60,100),
('Campus Backpack','Lightweight, durable, and ready for class.',899,20),
('Database Systems','Your companion to relational databases.',550,15),
('Study Planner','Make room for the work that matters.',199,30),
('Steel Water Bottle','Stay refreshed from lectures to the library.',399,25);
