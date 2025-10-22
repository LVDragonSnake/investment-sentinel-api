import os
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.get("/")
def root():
    return jsonify({"ok": True, "message": "Investment Sentinel API is live"})

@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "investment-sentinel-api"})

# --------- PLACEHOLDER ENDPOINTS (funzionanti) ----------
# Sostituiremo la logica appena è tutto live

@app.get("/finanzamille/digest")
def finanzamille_digest():
    # placeholder: torna una lista finta per verificare il wiring
    items = [
        {"title": "Esempio: Tassi in rialzo", "sentiment": "neutral", "topics": ["rates", "macro"]},
        {"title": "Esempio: Tech rimbalza", "sentiment": "positive", "topics": ["equities", "tech"]},
    ]
    return jsonify({"ok": True, "count": len(items), "items": items})

@app.get("/global/news")
def global_news():
    headlines = [
        "US: Powell speech at 2pm ET",
        "EU: PMI flash above consensus",
        "Asia: Nikkei flat into close",
    ]
    return jsonify({"ok": True, "headlines": headlines})

@app.post("/portfolio/csv")
def portfolio_csv():
    # Accetta CSV incollato nel body (content-type: text/plain oppure json {csv:"..."})
    csv_text = request.get_data(as_text=True) or (request.json or {}).get("csv", "")
    if not csv_text.strip():
        return jsonify({"ok": False, "error": "CSV mancante nel body"}), 400
    # placeholder: calcolo finto
    return jsonify({"ok": True, "positions": 10, "pnls": {"day": 12.34, "total": 345.67}})

@app.post("/alpaca/bridge")
def alpaca_bridge():
    # placeholder: verifica solo che le env esistano (non obbligatorie)
    have_keys = bool(os.environ.get("ALPACA_API_KEY")) and bool(os.environ.get("ALPACA_SECRET_KEY"))
    return jsonify({"ok": True, "keys_present": have_keys})

# ---------- MAIN (per local dev). In Render usa GUNICORN ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
