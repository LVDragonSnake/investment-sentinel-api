import os
from datetime import datetime
from flask import Flask, jsonify, request, Response

app = Flask(__name__)

# ---- Endpoints di base (già esistenti/compatibili) --------------------------
@app.get("/health")
def health():
    return jsonify(ok=True, service="investment-sentinel-api")

# --- FinanzAmille: digest (usa env e permette override via query) ---
@app.get("/finanzamille/digest")
def fm_digest():
    import os, re, requests
    from flask import request, jsonify

    base = os.getenv("FM_BASE_URL", "https://www.finanzamille.com").rstrip("/")
    cookie = os.getenv("FM_COOKIE", "")
    default_path = os.getenv("FM_CONTENT_PATH", "/corso-1-1")

    # Permetti override da query: ?path=/corso-1-1 oppure ?url=https://www.finanzamille.com/corso-1-1
    q_path = request.args.get("path")
    q_url = request.args.get("url")

    if q_url:
        target = q_url
    else:
        path = q_path or default_path or "/corso-1-1"
        if not path.startswith("/"):
            path = "/" + path
        target = f"{base}{path}"

    headers = {
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        r = requests.get(target, headers=headers, timeout=25, allow_redirects=True)
    except Exception as e:
        return jsonify({"ok": False, "error": f"request_error: {e}", "fetched_url": target}), 502

    # Se porta alla pagina login/403 -> cookie non valido
    if r.status_code in (401, 403) or "login" in r.url:
        return jsonify({"ok": False, "error": "unauthorized", "fetched_url": target, "final_url": r.url}), 401

    if r.status_code != 200:
        return jsonify({"ok": False, "error": f"http_{r.status_code}", "fetched_url": target, "final_url": r.url}), r.status_code

    # Estraggo solo il <title> per validare che stiamo leggendo la pagina protetta
    m = re.search(r"<title>(.*?)</title>", r.text, re.I | re.S)
    title = (m.group(1).strip() if m else "")

    return jsonify({
        "ok": True,
        "fetched_url": target,
        "final_url": r.url,
        "length": len(r.text),
        "title": title
    }), 200
# --- fine route ---

# --------- FinanzAmille helpers + routes: article & batch ---------
from bs4 import BeautifulSoup

def fm_fetch(target_url: str):
    import os, requests
    cookie = os.getenv("FM_COOKIE", "")
    headers = {
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    r = requests.get(target_url, headers=headers, timeout=25, allow_redirects=True)
    return r

def extract_article_fields(html: str):
    soup = BeautifulSoup(html, "html.parser")

    # Titolo: prova h1, poi title
    title = ""
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(strip=True)
    elif soup.title and soup.title.get_text(strip=True):
        title = soup.title.get_text(strip=True)

    # Corpo: prendi paragrafi dentro article, altrimenti tutti i <p> principali
    body_texts = []
    article_tag = soup.find("article")
    if article_tag:
        body_texts = [p.get_text(" ", strip=True) for p in article_tag.find_all("p")]
    if not body_texts:
        # Fallback generico
        candidates = soup.select("main p") or soup.find_all("p")
        body_texts = [p.get_text(" ", strip=True) for p in candidates]

    text = "\n".join([t for t in body_texts if t])

    # Mini-riassunto euristico (prime 3-4 frasi)
    summary = ""
    if text:
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        summary = ". ".join(sentences[:4]) + ("." if sentences[:4] else "")

    return title, text, summary

@app.get("/finanzamille/article")
def fm_article():
    from flask import request, jsonify
    import os

    base = os.getenv("FM_BASE_URL", "https://www.finanzamille.com").rstrip("/")
    url = request.args.get("url")
    if not url:
        return jsonify({"ok": False, "error": "missing url"}), 400
    if url.startswith("/"):
        url = base + url

    r = fm_fetch(url)
    if r.status_code in (401, 403) or "login" in r.url:
        return jsonify({"ok": False, "error": "unauthorized", "fetched_url": url, "final_url": r.url}), 401
    if r.status_code != 200:
        return jsonify({"ok": False, "error": f"http_{r.status_code}", "fetched_url": url, "final_url": r.url}), r.status_code

    title, text, summary = extract_article_fields(r.text)
    return jsonify({
        "ok": True,
        "url": url,
        "final_url": r.url,
        "title": title,
        "summary": summary,
        "chars": len(text)
    }), 200

@app.get("/finanzamille/batch")
def fm_batch():
    from flask import request, jsonify
    import os

    base = os.getenv("FM_BASE_URL", "https://www.finanzamille.com").rstrip("/")
    urls = request.args.getlist("url")
    if not urls:
        return jsonify({"ok": False, "error": "missing url params"}), 400

    items = []
    for u in urls:
        full = base + u if u.startswith("/") else u
        try:
            r = fm_fetch(full)
            if r.status_code == 200 and "login" not in r.url:
                title, text, summary = extract_article_fields(r.text)
                items.append({"ok": True, "url": full, "title": title, "summary": summary})
            else:
                items.append({"ok": False, "url": full, "status": r.status_code, "final_url": r.url})
        except Exception as e:
            items.append({"ok": False, "url": full, "error": str(e)})

    return jsonify({"ok": True, "count": len(items), "items": items}), 200
# --------- fine blocco ---------

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
