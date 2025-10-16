# sasya-yojana-AI-agent
# 🌿 Sasya Yojana – AI-Based Land Use Planner

**Sasya Yojana** is an AI-driven web platform designed to assist small and marginal farmers in planning sustainable land use.  
By analyzing inputs such as rainfall, soil pH, and investment level, the system recommends optimal **primary crops**, **intercrops**, and **boundary trees** — helping farmers maximize productivity while maintaining ecological balance.

---

## 🚜 Problem Statement

Indian farmers face challenges in:
- Selecting suitable crops for varying rainfall and soil conditions.  
- Balancing economic returns with soil and water sustainability.  
- Accessing localized, AI-driven guidance in their preferred language.  

**Sasya Yojana** solves these by integrating **AI**, **data visualization**, and **multilingual support** into a user-friendly tool that creates real-time land-use plans.

---

## 💡 Features

- 🌱 **AI-Powered Recommendations** — Suggests best crops and trees based on environment and investment level.  
- 🗺️ **Interactive Farm Layout (D3.js)** — Visual grid map showing crop and tree arrangements.  
- 💬 **Multilingual Voice Narration** — English, Hindi, Kannada, and Marathi support via SpeechSynthesis API.  
- 📊 **Economic Analysis** — Calculates expected yield, cost, and profit for each crop.  
- 🧾 **Plan Export** — Download results as **PDF**, **JSON**, or **SVG** for offline use.  
- 🧠 **AI Agent Blueprint** — Modular structure ready for future ML integration.  

---

## 🧩 Project Architecture

Setting up backend
cd backend
python -m venv venv
source venv/bin/activate   # (on macOS/Linux)
venv\Scripts\activate      # (on Windows)
pip install -r requirements.txt
python app.py
