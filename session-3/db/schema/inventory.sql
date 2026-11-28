CREATE TABLE suppliers (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, lead_time_days INTEGER NOT NULL, min_order_value REAL NOT NULL
);
CREATE TABLE products (
  id INTEGER PRIMARY KEY, sku TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
  unit_cost REAL NOT NULL, supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
  stock_on_hand INTEGER NOT NULL, on_order INTEGER NOT NULL DEFAULT 0, reorder_point INTEGER NOT NULL
);
CREATE TABLE demand_history (
  product_id INTEGER NOT NULL REFERENCES products(id), week_start TEXT NOT NULL,
  units INTEGER NOT NULL, PRIMARY KEY (product_id, week_start)
);
CREATE TABLE purchase_orders (
  id INTEGER PRIMARY KEY, supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
  status TEXT NOT NULL DEFAULT 'pending_approval' CHECK (status IN ('pending_approval','approved','rejected')),
  total REAL NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, decided_by TEXT
);
CREATE TABLE po_lines (
  po_id INTEGER NOT NULL REFERENCES purchase_orders(id), product_id INTEGER NOT NULL REFERENCES products(id),
  qty INTEGER NOT NULL, unit_cost REAL NOT NULL, PRIMARY KEY (po_id, product_id)
);
