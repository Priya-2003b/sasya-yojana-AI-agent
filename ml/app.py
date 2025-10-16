# backend/app.py
import os
import sqlite3
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Import DB helpers
from backend.db import init_db, seed_data, get_db, ensure_plans_table, ensure_labels_table, save_labels_for_plan

# ---------------- App Init ----------------
app = Flask(__name__, static_folder="../frontend", static_url_path="/")
CORS(app)

# Optional blueprints
try:
    from backend.pdf_service import pdf_bp
    app.register_blueprint(pdf_bp)
except Exception as e:
    print("pdf_service not registered:", str(e))

try:
    from backend.vosk_service import vosk_bp
    app.register_blueprint(vosk_bp)
except Exception as e:
    print("vosk_service not registered:", str(e))

try:
    from backend.stt_service import stt_bp
    app.register_blueprint(stt_bp)
except Exception as e:
    print("stt_service not registered:", str(e))

# ---------------- Config & DB ----------------
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sasya.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
init_db(DB_PATH)
seed_data(DB_PATH)
ensure_labels_table(DB_PATH)

# ---------------- Endpoints ----------------
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
    cur = db.execute("SELECT id,name,drought_tolerance,canopy_m,spacing_m,uses FROM trees")
    rows = [dict(r) for r in cur.fetchall()]
    db.close()
    return jsonify({"status": "ok", "count": len(rows), "rows": rows})


@app.route("/api/generate_plan", methods=["POST"])
def generate_plan():
    """Generate a labeled plan with per-cell metadata and basic economics."""
    payload = request.json or {}
    db = get_db(DB_PATH)

    rainfall = float(payload.get("rainfall_mm", payload.get("rainfall", 400)))
    area_m2 = float(payload.get("area_m2", payload.get("area", 8000)))
    soil_ph = float(payload.get("soil_ph", 6.5))
    investment_level = payload.get("investment_level", payload.get("investment", "low"))

    # Crop selection by rainfall
    cur = db.execute(
        "SELECT * FROM crops WHERE min_rainfall <= ? AND max_rainfall >= ? ORDER BY typical_yield_kg_per_ha DESC",
        (rainfall, rainfall),
    )
    candidates = cur.fetchall()
    if not candidates:
        cur = db.execute("SELECT * FROM crops ORDER BY typical_yield_kg_per_ha DESC")
        candidates = cur.fetchall()

    primary = dict(candidates[0]) if candidates else {"name": "Unknown"}
    intercrop = dict(candidates[1]) if len(candidates) > 1 else dict(candidates[0]) if candidates else {"name": "Unknown"}

    # Tree selection
    cur = db.execute(
        "SELECT * FROM trees ORDER BY CASE drought_tolerance WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, spacing_m ASC LIMIT 1"
    )
    tree = cur.fetchone()
    tree = dict(tree) if tree else None

    # Layout with metadata
    cell_size_m = 4.0
    side_m = area_m2 ** 0.5
    cols = max(3, int(side_m // cell_size_m))
    rows = max(3, int(area_m2 // (cols * cell_size_m)))
    if rows < 3:
        rows = cols

    layout_cells = []
    for r in range(rows):
        for c in range(cols):
            cell_id = f"r{r}_c{c}"
            x_m = round(c * cell_size_m, 2)
            y_m = round(r * cell_size_m, 2)
            if r in [0, rows - 1] or c in [0, cols - 1]:
                species = tree["name"] if tree else None
                cell_type = "tree"
            else:
                species = primary["name"] if r % 2 == 0 else intercrop["name"]
                cell_type = "crop"

            layout_cells.append(
                {
                    "cell_id": cell_id,
                    "r": r,
                    "c": c,
                    "type": cell_type,
                    "species": species,
                    "x_m": x_m,
                    "y_m": y_m,
                    "area_m2": round(cell_size_m * cell_size_m, 2),
                }
            )

    # Economics
    species_area = {}
    for cell in layout_cells:
        sp = cell["species"] or "unknown"
        species_area.setdefault(sp, 0)
        species_area[sp] += cell["area_m2"]

    economics = {"by_species": {}, "total_revenue": 0.0, "total_cost": 0.0, "total_net": 0.0}
    for sp, area in species_area.items():
        cur = db.execute("SELECT * FROM crops WHERE name = ? LIMIT 1", (sp,))
        crop = cur.fetchone()
        if crop:
            ha = area / 10000.0
            yield_kg = crop["typical_yield_kg_per_ha"] * ha
            revenue = yield_kg * crop["market_price_per_kg"]
            cost = crop["input_cost_per_ha"] * ha
            net = revenue - cost
            economics["by_species"][sp] = {
                "area_m2": round(area, 2),
                "yield_kg": round(yield_kg, 2),
                "revenue": round(revenue, 2),
                "cost": round(cost, 2),
                "net": round(net, 2),
                "cell_count": int(area / (cell_size_m * cell_size_m)),
            }
            economics["total_revenue"] += revenue
            economics["total_cost"] += cost
            economics["total_net"] += net
        else:
            economics["by_species"][sp] = {
                "area_m2": round(area, 2),
                "notes": "Tree or non-crop: long-term benefits",
            }

    db.close()

    return jsonify(
        {
            "status": "ok",
            "input": payload,
            "primary_crop": primary,
            "intercrop": intercrop,
            "boundary_tree": tree,
            "layout": {"rows": rows, "cols": cols, "cell_size_m": cell_size_m, "cells": layout_cells},
            "economics": economics,
            "explanation": {
                "method": "rule-based fallback for now (later: AI agent)",
                "selected_by": "rainfall + heuristics",
            },
        }
    )


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/save_plan", methods=["POST"])
def save_plan():
    payload = request.json or {}
    farmer_name = payload.get("farmer_name") or (payload.get("input", {}) or {}).get("name") or "Unknown"
    plan_json = payload.get("plan") or payload

    ensure_plans_table(DB_PATH)
    ensure_labels_table(DB_PATH)

    import json
    plan_text = json.dumps(plan_json, ensure_ascii=False)

    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.execute("INSERT INTO plans (farmer_name, plan_json) VALUES (?, ?)", (farmer_name, plan_text))
    db.commit()
    plan_id = cur.lastrowid
    db.close()

    # Save labels for this plan
    try:
        if "layout" in plan_json and "cells" in plan_json["layout"]:
            layout_cells = plan_json["layout"]["cells"]
            save_labels_for_plan(DB_PATH, plan_id, layout_cells)
    except Exception as e:
        print("⚠️ Warning: could not save labels:", e)

    return jsonify({"status": "ok", "message": "Plan saved", "plan_id": plan_id})


# ---------------- Run ----------------
if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
