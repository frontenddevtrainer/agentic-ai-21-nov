CREATE TABLE customers (
  id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL, plan TEXT NOT NULL
);
CREATE TABLE orders (
  id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
  item TEXT NOT NULL, total REAL NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('processing','shipped','delivered','lost','refunded')),
  placed_at TEXT NOT NULL, tracking TEXT
);
CREATE TABLE refunds (
  id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id),
  amount REAL NOT NULL, reason TEXT NOT NULL, approved_by TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE tickets (
  id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id),
  category TEXT NOT NULL, priority TEXT NOT NULL DEFAULT 'normal', summary TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
