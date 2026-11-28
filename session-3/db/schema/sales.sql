CREATE TABLE customers (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, country TEXT NOT NULL,
  segment TEXT NOT NULL CHECK (segment IN ('consumer','smb','enterprise')),
  created_at TEXT NOT NULL
);
CREATE TABLE products (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, price REAL NOT NULL
);
CREATE TABLE orders (
  id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
  ordered_at TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('paid','refunded','cancelled'))
);
CREATE TABLE order_items (
  order_id INTEGER NOT NULL REFERENCES orders(id), product_id INTEGER NOT NULL REFERENCES products(id),
  qty INTEGER NOT NULL, unit_price REAL NOT NULL, PRIMARY KEY (order_id, product_id)
);