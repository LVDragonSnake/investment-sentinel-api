import os
import re
from datetime import datetime
from flask import Flask, jsonify, request, Response
from bs4 import BeautifulSoup
import requests

app = Flask(__name__)

# -----------------------------------------------------------------------------
# Health
# -----------------------------------------------------------------------------
@app.get("/health")
def health():
    return jsonify(ok=True, service="investment-sentinel-api")

# -----------------------------------------------------------------------------
# FinanzAmille: digest (usa env e permette override via query)
# -----------------------------------------------------------------------------
@app.get("/finanzamille/digest")
def fm_digest():
    base = os.getenv("FM_BASE_URL", "https://www.finanzamille.com").rstrip("/")
    cookie = os.getenv("FM_COOKIE", "")
    default_path = os.getenv("FM_CONTENT_PATH", "/corso-1-1")

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

    if r.status_code in (401, 403) or "login" in r.url.lower():
        return jsonify({"ok": False, "error": "unauthorized", "fetched_url": target, "final_url": r.url}), 401

    if r.status_code != 200:
        return jsonify({"ok": False, "error": f"http_{r.status_code}", "fetched_url": target, "final_url": r.url}), r.status_code

    m = re.search(r"<title>(.*?)</title>", r.text, re.I | re.S)
    title = (m.group(1).strip() if m else "")

    return jsonify({
        "ok": True,
        "fetched_url": target,
        "final_url": r.url,
        "length": len(r.text),
        "title": title
    }), 200

# -----------------------------------------------------------------------------
# FinanzAmille: helpers + routes: article e batch
# -----------------------------------------------------------------------------
def fm_fetch(target_url: str):
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

    # Corpo: paragrafi dentro <article>, altrimenti fallback ai <p> principali
    body_texts = []
    article_tag = soup.find("article")
    if article_tag:
        body_texts = [p.get_text(" ", strip=True) for p in article_tag.find_all("p")]
    if not body_texts:
        candidates = soup.select("main p") or soup.find_all("p")
        body_texts = [p.get_text(" ", strip=True) for p in candidates]

    text = "\n".join([t for t in body_texts if t])

    # Mini riassunto euristico: prime 3-4 frasi
    summary = ""
    if text:
        sentences = [s.strip() for s in text.split(".") if s.strip()]
        summary = ". ".join(sentences[:4]) + ("." if sentences[:4] else "")

    return title, text, summary

@app.get("/finanzamille/article")
def fm_article():
    base = os.getenv("FM_BASE_URL", "https://www.finanzamille.com").rstrip("/")
    url = request.args.get("url")
    if not url:
        return jsonify({"ok": False, "error": "missing url"}), 400
    if url.startswith("/"):
        url = base + url

    r = fm_fetch(url)
    if r.status_code in (401, 403) or "login" in r.url.lower():
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
    base = os.getenv("FM_BASE_URL", "https://www.finanzamille.com").rstrip("/")
    urls = request.args.getlist("url")
    if not urls:
        return jsonify({"ok": False, "error": "missing url params"}), 400

    items = []
    for u in urls:
        full = base + u if u.startswith("/") else u
        try:
            r = fm_fetch(full)
            if r.status_code == 200 and "login" not in r.url.lower():
                title, text, summary = extract_article_fields(r.text)
                items.append({"ok": True, "url": full, "title": title, "summary": summary})
            else:
                items.append({"ok": False, "url": full, "status": r.status_code, "final_url": r.url})
        except Exception as e:
            items.append({"ok": False, "url": full, "error": str(e)})

    return jsonify({"ok": True, "count": len(items), "items": items}), 200

# -----------------------------------------------------------------------------
# News: stub macro PM USA
# -----------------------------------------------------------------------------
@app.get("/news/scan")
def news_scan():
    region = request.args.get("region", "us")
    window = request.args.get("window", "6h")
    items = [
        {"headline": "Fed officials: higher for longer sul tavolo", "tags": ["rates", "fed"], "impact": "medium"},
        {"headline": "NASDAQ verde nel pomeriggio", "tags": ["tech", "equities"], "impact": "low"},
    ]
    return jsonify(ok=True, region=region, window=window, items=items)

# -----------------------------------------------------------------------------
# Alpaca: health placeholder
# -----------------------------------------------------------------------------
@app.get("/alpaca/health")
def alpaca_health():
    return jsonify(ok=True, broker="alpaca", connected=False)

# -----------------------------------------------------------------------------
# Brief: aggregatore (in-process, no HTTP interni)
# -----------------------------------------------------------------------------
def build_brief_payload():
    """Raccoglie tutto in JSON senza chiamate HTTP interne."""
    fm_urls_env = os.getenv("FM_URLS", "").strip()
    fm_items = []

    if fm_urls_env:
        fm_list = [u.strip() for u in fm_urls_env.split(",") if u.strip()]
        for u in fm_list:
            # Normalizza eventuali path relativi
            if u.startswith("/"):
                base = os.getenv("FM_BASE_URL", "https://www.finanzamille.com").rstrip("/")
                full = base + u
            else:
                full = u
            try:
                r = fm_fetch(full)
                if r.status_code == 200 and "login" not in r.url.lower():
                    title, text, summary = extract_article_fields(r.text)
                    fm_items.append({"ok": True, "url": full, "title": title, "summary": summary})
                else:
                    fm_items.append({"ok": False, "url": full, "status": r.status_code, "final_url": r.url})
            except Exception as e:
                fm_items.append({"ok": False, "url": full, "error": str(e)})

    nws = news_scan().get_json()
    alp = alpaca_health().get_json()

    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return {
        "ok": True,
        "generated_at": ts,
        "finanzamille": {"items": fm_items},
        "news": nws,
        "alpaca": alp
    }

@app.get("/brief/run")
def brief_run():
    return jsonify(build_brief_payload())

@app.get("/brief/text")
def brief_text():
    data = build_brief_payload()
    lines = []
    lines.append(f"[Investment Sentinel] Brief - {data['generated_at']}")
    lines.append("")

    # FinanzAmille
    lines.append("FinanzAmille (oggi)")
    items = data.get("finanzamille", {}).get("items", [])
    if items:
        for it in items:
            title = (it.get("title") or "").strip()
            summary = (it.get("summary") or "").strip().replace("\n", " ")
            if title or summary:
                lines.append(f"* {title} - {summary[:220]}")
    else:
        lines.append("* Nessun articolo disponibile o accesso non valido")
    lines.append("")

    # News
    lines.append("Mercati (PM USA)")
    news_items = data.get("news", {}).get("items", [])
    if news_items:
        for it in news_items:
            headline = it.get("headline", "")
            impact = it.get("impact", "")
            if headline:
                lines.append(f"* {headline} [{impact}]")
    else:
        lines.append("* Nessun aggiornamento macro disponibile")
    lines.append("")

    # Broker
    alp = data.get("alpaca", {})
    lines.append(f"Broker: Alpaca connected={alp.get('connected', False)}")
    lines.append("")

    # Azioni proposte - placeholder conservativo
    lines.append("Azioni proposte")
    lines.append("* Nessuna urgenza. Mantieni profilo prudente. Per piazzare ordini rispondi con CONFERMO e dettagli.")

    txt = "\n".join(lines)
    return Response(txt, mimetype="text/plain")

# -----------------------------------------------------------------------------
# Wrapper comodi (in-process)
# -----------------------------------------------------------------------------
@app.get("/brief/direct")
def brief_direct():
    try:
        return brief_text()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/wake")
def wake():
    try:
        return brief_text()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502

# -----------------------------------------------------------------------------
# Avvio WSGI (solo esecuzione diretta)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
