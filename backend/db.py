# backend/db.py
import sqlite3
import os

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS crops (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT,
  min_rainfall INTEGER,
  max_rainfall INTEGER,
  season TEXT,
  typical_yield_kg_per_ha REAL,
  input_cost_per_ha REAL,
  market_price_per_kg REAL
);

CREATE TABLE IF NOT EXISTS trees (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT,
  drought_tolerance TEXT,
  canopy_m REAL,
  spacing_m REAL,
  uses TEXT
);
"""

SEED_CROPS = [
  ("Pearl Millet",200,600,"Kharif",800,10000,10),
  ("Sorghum",300,800,"Kharif",1200,12000,9),
  ("Pigeon Pea",300,900,"Kharif/Rabi",700,9000,22),
  ("Greengram",300,700,"Kharif",500,7000,30),
  ("Sesame",250,600,"Kharif",400,6000,40),
  ("Groundnut",400,900,"Kharif",2000,15000,18),
  ("Horsegram",250,700,"Kharif",600,5000,20),
  ("Cowpea",300,800,"Kharif",700,6000,20),
]

SEED_TREES = [
  ("Neem","high",8,8,"boundary, pest control, medicinal"),
  ("Tamarind","medium",10,10,"fruit, boundary"),
  ("Gliricidia","high",4,2.5,"fodder, nitrogen fixer"),
  ("Mahogany","low",12,12,"timber, shade"),
]

def get_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    with conn:
        conn.executescript(SCHEMA_SQL)
    conn.close()

def seed_data(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # ensure tables exist
    cur.executescript(SCHEMA_SQL)
    # seed crops if empty
    cur.execute("SELECT COUNT(1) as cnt FROM crops")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO crops (name,min_rainfall,max_rainfall,season,typical_yield_kg_per_ha,input_cost_per_ha,market_price_per_kg) VALUES (?,?,?,?,?,?,?)",
            SEED_CROPS
        )
    # seed trees if empty
    cur.execute("SELECT COUNT(1) as cnt FROM trees")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO trees (name,drought_tolerance,canopy_m,spacing_m,uses) VALUES (?,?,?,?,?)",
            SEED_TREES
        )

    conn.commit()
    conn.close()

# ----------------- Plans table -----------------
def ensure_plans_table(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS plans (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      farmer_name TEXT,
      plan_json TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    );
    """)
    conn.commit()
    conn.close()

# ----------------- Labels table & helpers -----------------
def ensure_labels_table(db_path):
    """
    Create labels table if not exists.
    Stores cell-level metadata for each saved plan.
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS labels (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      plan_id INTEGER NOT NULL,
      cell_id TEXT NOT NULL,
      r INTEGER,
      c INTEGER,
      type TEXT,
      species TEXT,
      x_m REAL,
      y_m REAL,
      area_m2 REAL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    conn.close()

def save_labels_for_plan(db_path, plan_id, layout_cells):
    """
    Insert layout cell rows for a saved plan.
    layout_cells: list of dicts each containing
      cell_id, r, c, type, species, x_m, y_m, area_m2
    """
    if not layout_cells:
        return
    ensure_labels_table(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    rows = []
    for c in layout_cells:
        rows.append((
          plan_id,
          c.get("cell_id"),
          c.get("r"),
          c.get("c"),
          c.get("type"),
          c.get("species"),
          c.get("x_m"),
          c.get("y_m"),
          c.get("area_m2")
        ))
    cur.executemany("""
      INSERT INTO labels (plan_id, cell_id, r, c, type, species, x_m, y_m, area_m2)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    conn.close()

def get_labels_for_plan(db_path, plan_id):
    """
    Return list of label dicts for a given plan_id.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT cell_id, r, c, type, species, x_m, y_m, area_m2 FROM labels WHERE plan_id = ? ORDER BY id ASC", (plan_id,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows
