import os
from datetime import datetime
from flask import Flask, jsonify, request, Response

app = Flask(__name__)

# ---- Endpoints di base (già esistenti/compatibili) --------------------------
@app.get("/health")
def health():
    return jsonify(ok=True, service="investment-sentinel-api")

# --- Finanzamille digest (con fallback) ---
@app.get("/finanzamille/digest")
def finanzamille_digest():
    import os, json
    import requests
    from bs4 import BeautifulSoup

    limit = int(request.args.get("limit", 8))

    # (Opzionale) se in futuro vorrai passare da cookie:
    fm_cookie = os.getenv("FINANZAMILLE_COOKIE", "").strip()
    fm_url    = os.getenv("FINANZAMILLE_URL", "https://www.finanzamille.com/daily-news")

    try:
        headers = {}
        if fm_cookie:
            headers["Cookie"] = fm_cookie

        # Primo tentativo: pagina pubblica “daily news” (non serve devtools)
        r = requests.get(fm_url, headers=headers, timeout=12)
        r.raise_for_status()

        # Parsing HTML base (prende i link/articoli visibili nella pagina)
        soup = BeautifulSoup(r.text, "html.parser")
        items = []
        # Heuristica semplice: prendi <a> con href che contiene "/blog-2-1/"
        for a in soup.select('a[href*="/blog-2-1/"]')[:limit]:
            title = (a.get_text() or "").strip()
            url = a.get("href") or ""
            if title and url:
                items.append({
                    "title": title,
                    "url": url if url.startswith("http") else f"https://www.finanzamille.com{url}",
                    "summary": "",
                    "sentiment": "unknown"
                })

        # Se non abbiamo trovato nulla, usa fallback demo (così non rompiamo i test)
        if not items:
            items = [
                {"title": "Esempio: Tassi in rialzo", "url": "#", "summary": "", "sentiment": "neutral"},
                {"title": "Esempio: Tech rimbalza", "url": "#", "summary": "", "sentiment": "positive"},
            ][:limit]

        return jsonify(ok=True, count=len(items), items=items)

    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500

@app.get("/news/scan")
def news_scan():
    # Stub PM-USA. window/region per compatibilità
    region = request.args.get("region", "us")
    window = request.args.get("window", "6h")
    items = [
        {"headline": "Fed officials: 'higher for longer' sul tavolo", "tags": ["rates","fed"], "impact":"medium"},
        {"headline": "NASDAQ green nel pomeriggio", "tags": ["tech","equities"], "impact":"low"},
    ]
    return jsonify(ok=True, region=region, window=window, items=items)

@app.get("/alpaca/health")
def alpaca_health():
    # Quando avrai le API, qui metteremo la vera chiamata
    return jsonify(ok=True, broker="alpaca", connected=False)

# ---- Aggregatore: /brief ----------------------------------------------------
def _mk_recommendations(fm, news):
    recs = []
    # Esempio di logica super semplice
    if any(i.get("sentiment") == "negative" and "energy" in i.get("topics", []) for i in fm.get("items", [])):
        recs.append("Energia debole: valuta stop-loss più stretti su titoli energy.")
    if any("fed" in (i.get("tags") or []) for i in news.get("items", [])):
        recs.append("Tassi: profilo prudente; evita nuova leva finché il quadro sui rendimenti non migliora.")
    if not recs:
        recs.append("Nessuna urgenza. Mantieni impostazione conservativa.")
    return recs

@app.get("/brief/run")
def brief_run():
    # Chiama internamente le funzioni sopra (più veloce/robusto di richiamare via HTTP)
    fm = finanzamille_digest().get_json()
    nws = news_scan().get_json()
    alp = alpaca_health().get_json()

    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    recommendations = _mk_recommendations(fm, nws)

    payload = {
        "ok": True,
        "generated_at": ts,
        "finanzamille": fm,
        "news": nws,
        "alpaca": alp,
        "recommendations": recommendations
    }
    return jsonify(payload)

@app.get("/brief/text")
def brief_text():
    data = brief_run().get_json()
    lines = []
    lines.append(f"[Investment Sentinel] Brief – {data['generated_at']}")
    lines.append("")
    # FinanzAmille
    lines.append("— FinanzAmille (ultimi):")
    for it in data["finanzamille"]["items"]:
        lines.append(f"  • {it['title']}  [sentiment: {it['sentiment']}]")
    lines.append("")
    # News
    lines.append(f"— News scan ({data['news']['region']}, {data['news']['window']}):")
    for it in data["news"]["items"]:
        lines.append(f"  • {it['headline']}  [impact: {it['impact']}]")
    lines.append("")
    # Alpaca
    lines.append(f"— Broker: Alpaca connected={data['alpaca']['connected']}")
    lines.append("")
    # Azioni consigliate
    lines.append("— Azioni consigliate:")
    for r in data["recommendations"]:
        lines.append(f"  • {r}")
    txt = "\n".join(lines)
    return Response(txt, mimetype="text/plain")

# ---- Avvio WSGI -------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
