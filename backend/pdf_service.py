from fpdf import FPDF
from flask import Blueprint, request, send_file
import io, datetime

pdf_bp = Blueprint("pdf_bp", __name__)

@pdf_bp.route("/api/pdf_plan", methods=["POST"])
def make_pdf():
    data = request.get_json(force=True)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Sasya Yojana Land Plan", ln=True, align="C")
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"Farmer: {data['input'].get('name','')}", ln=True)
    pdf.cell(0, 10, f"Area: {data['input'].get('area_m2','')} m²", ln=True)
    pdf.ln(5)
    pdf.cell(0, 10, "Crops & Trees:", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 8,
        f"Boundary tree: {data['boundary_tree'].get('name','')}\n"
        f"Primary crop: {data['primary_crop'].get('name','')}\n"
        f"Intercrop: {data['intercrop'].get('name','')}")
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Action Plan", ln=True)
    pdf.set_font("Arial", size=11)
    steps = [
        f"Plant {data['boundary_tree'].get('name','trees')} around boundary.",
        f"Prepare land and add compost.",
        f"Sow {data['primary_crop'].get('name','')} with {data['intercrop'].get('name','')} in rows.",
        "Mulch soil and irrigate during dry spells.",
        "Use organic pest repellents.",
        "Harvest and record yields."
    ]
    for i, s in enumerate(steps, 1):
        pdf.multi_cell(0, 8, f"{i}. {s}")
    pdf.ln(10)
    pdf.set_font("Arial", "I", 10)
    pdf.cell(0, 10, "Generated on " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), ln=True)
    stream = io.BytesIO(pdf.output(dest="S").encode("latin1"))
    stream.seek(0)
    return send_file(stream, as_attachment=True, download_name="SasyaPlan.pdf", mimetype="application/pdf")
