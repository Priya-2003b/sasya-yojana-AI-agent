# backend/app.py
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import sqlite3
import json
from backend.db import (
    init_db,
    seed_data,
    get_db,
    ensure_plans_table,
    save_labels_for_plan,
    get_labels_for_plan,
)

# ----------------- Initialization -----------------
app = Flask(__name__, static_folder="../frontend", static_url_path="/")
CORS(app)

# ✅ --- Register AI Agent Blueprint (ADDED) ---
try:
    from backend.agent_service import agent_bp
    app.register_blueprint(agent_bp)
    print("✅ AI Agent Blueprint registered successfully.")
except Exception as e:
    print("⚠️ Could not register agent_service:", str(e))
# --------------------------------------------------

# ✅ Optional PDF support
try:
    from backend.pdf_service import pdf_bp
    app.register_blueprint(pdf_bp)
except Exception as e:
    print("pdf_service not registered:", str(e))

# ----------------- Database Setup -----------------
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sasya.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
init_db(DB_PATH)
seed_data(DB_PATH)

# ----------------- Endpoints -----------------
@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "sasya-backend"})

@app.route("/api/crops")
def list_crops():
    db = get_db(DB_PATH)
    cur = db.execute(
        "SELECT id,name,min_rainfall,max_rainfall,typical_yield_kg_per_ha,market_price_per_kg,input_cost_per_ha FROM crops"
    )
    rows = [dict(r) for r in cur.fetchall()]
    db.close()
    return jsonify({"status": "ok", "count": len(rows), "rows": rows})

@app.route("/api/trees")
def list_trees():
    db = get_db(DB_PATH)
    cur = db.execute(
        "SELECT id,name,drought_tolerance,canopy_m,spacing_m,uses FROM trees"
    )
    rows = [dict(r) for r in cur.fetchall()]
    db.close()
    return jsonify({"status": "ok", "count": len(rows), "rows": rows})

@app.route("/api/generate_plan", methods=["POST"])
def generate_plan():
    """Rule-based plan generator (AI integration-ready)"""
    payload = request.json or {}
    db = get_db(DB_PATH)

    rainfall = float(payload.get("rainfall_mm", payload.get("rainfall", 400)))
    area_m2 = float(payload.get("area_m2", 8000))
    soil_ph = float(payload.get("soil_ph", 6.5))
    investment = payload.get("investment_level", payload.get("investment", "low"))

    # Select crops
    cur = db.execute(
        "SELECT * FROM crops WHERE min_rainfall <= ? AND max_rainfall >= ? ORDER BY typical_yield_kg_per_ha DESC",
        (rainfall, rainfall),
    )
    crops = cur.fetchall()
    if not crops:
        cur = db.execute(
            "SELECT * FROM crops ORDER BY typical_yield_kg_per_ha DESC LIMIT 5"
        )
        crops = cur.fetchall()

    primary = dict(crops[0]) if crops else {"name": "Unknown"}
    intercrop = dict(crops[1]) if len(crops) > 1 else dict(crops[0])

    # Select tree
    cur = db.execute(
        "SELECT * FROM trees ORDER BY CASE drought_tolerance WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, spacing_m ASC LIMIT 1"
    )
    tree = cur.fetchone()
    tree = dict(tree) if tree else {"name": "Neem", "spacing_m": 8}

    # Generate layout grid
    cell_size_m = 4.0
    side_m = area_m2 ** 0.5
    cols = max(3, int(side_m // cell_size_m))
    rows = max(3, int(area_m2 // (cols * cell_size_m)))
    if rows < 3:
        rows = cols

    layout = []
    for r in range(rows):
        for c in range(cols):
            cell_id = f"r{r}_c{c}"
            x_m = round(c * cell_size_m, 2)
            y_m = round(r * cell_size_m, 2)
            if r in (0, rows - 1) or c in (0, cols - 1):
                cell_type = "tree"
                species = tree["name"]
            else:
                cell_type = "crop"
                species = primary["name"] if r % 2 == 0 else intercrop["name"]
            layout.append(
                {
                    "cell_id": cell_id,
                    "r": r,
                    "c": c,
                    "type": cell_type,
                    "species": species,
                    "x_m": x_m,
                    "y_m": y_m,
                    "area_m2": cell_size_m * cell_size_m,
                }
            )

    # Economics
    econ = {"by_species": {}, "total_revenue": 0, "total_cost": 0, "total_net": 0}
    for cell in layout:
        sp = cell["species"]
        cur = db.execute("SELECT * FROM crops WHERE name=? LIMIT 1", (sp,))
        crop = cur.fetchone()
        if crop:
            ha = cell["area_m2"] / 10000.0
            yield_kg = crop["typical_yield_kg_per_ha"] * ha
            revenue = yield_kg * crop["market_price_per_kg"]
            cost = crop["input_cost_per_ha"] * ha
            net = revenue - cost
            if sp not in econ["by_species"]:
                econ["by_species"][sp] = {
                    "area_m2": 0,
                    "revenue": 0,
                    "cost": 0,
                    "net": 0,
                    "yield_kg": 0,
                }
            econ["by_species"][sp]["area_m2"] += cell["area_m2"]
            econ["by_species"][sp]["yield_kg"] += yield_kg
            econ["by_species"][sp]["revenue"] += revenue
            econ["by_species"][sp]["cost"] += cost
            econ["by_species"][sp]["net"] += net
            econ["total_revenue"] += revenue
            econ["total_cost"] += cost
            econ["total_net"] += net
    db.close()

    return jsonify(
        {
            "status": "ok",
            "input": payload,
            "primary_crop": primary,
            "intercrop": intercrop,
            "boundary_tree": tree,
            "layout": {
                "rows": rows,
                "cols": cols,
                "cell_size_m": cell_size_m,
                "cells": layout,
            },
            "economics": econ,
            "explanation": {
                "method": "Rule-based fallback (AI model integration pending)"
            },
        }
    )

@app.route("/api/save_plan", methods=["POST"])
def save_plan():
    payload = request.json or {}
    farmer_name = (
        payload.get("farmer_name")
        or (payload.get("input", {}) or {}).get("name")
        or "Unknown"
    )
    plan_json = payload.get("plan") or payload

    ensure_plans_table(DB_PATH)
    plan_text = json.dumps(plan_json, ensure_ascii=False)

    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.execute(
        "INSERT INTO plans (farmer_name, plan_json) VALUES (?, ?)",
        (farmer_name, plan_text),
    )
    db.commit()
    plan_id = cur.lastrowid
    db.close()

    # Save labels
    try:
        layout_cells = plan_json.get("layout", {}).get("cells", [])
        if layout_cells:
            save_labels_for_plan(DB_PATH, plan_id, layout_cells)
    except Exception as e:
        print("Warning: could not save labels:", e)

    return jsonify({"status": "ok", "message": "Plan saved", "plan_id": plan_id})

@app.route("/api/labels/<int:plan_id>", methods=["GET"])
def get_labels(plan_id):
    try:
        rows = get_labels_for_plan(DB_PATH, plan_id)
        return jsonify({"status": "ok", "plan_id": plan_id, "count": len(rows), "labels": rows})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ----------------- New: dashboard route -----------------
@app.route("/dashboard")
@app.route("/dashboard.html")
def dashboard():
    # serve the dashboard.html file located in frontend/
    return send_from_directory(app.static_folder, "dashboard.html")

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

# ----------------- Run -----------------
if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
