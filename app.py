import os, datetime as dt
from flask import Flask, request, jsonify
import re
import requests

app = Flask(__name__)

# ---- Helpers -------------------------------------------------
def is_valid_fm_link(url: str) -> bool:
    # accetta solo gli articoli reali
    return bool(re.search(r"https?://(www\.)?finanzamille\.com/blog-2-1/[\w-]+", url))

def now_utc_iso():
    return dt.datetime.utcnow().replace(microsecond=0).isoformat()+"Z"

# ---- Root & Health ------------------------------------------
@app.get("/")
def root():
    return jsonify(ok=True, service="investment-sentinel-api", time=now_utc_iso())

@app.get("/health")
def health():
    return jsonify(ok=True, service="investment-sentinel-api")

# ---- FinanzAmille digest ------------------------------------
@app.get("/finanzamille/digest")
def finanzamille_digest():
    """
    Ritorna ultimi articoli (titolo, url). Usa lista/landing pubbliche e filtra i link veri.
    Parametri: limit (default 5)
    """
    limit = int(request.args.get("limit", 5))
    # Pagine note che elencano articoli; se ne hai altre, aggiungile
    seeds = [
        "https://www.finanzamille.com/daily-news",     # calendario articoli
        "https://www.finanzamille.com",                # home
    ]

    items = []
    seen = set()
    headers = {"User-Agent": "Mozilla/5.0"}
    for seed in seeds:
        try:
            html = requests.get(seed, headers=headers, timeout=12).text
        except Exception:
            continue
        # estrai link + anchor testuale grezza
        for m in re.finditer(r'href="([^"]+)"[^>]*>([^<]{3,120})</a>', html, flags=re.I):
            url, text = m.group(1), re.sub(r"\s+", " ", m.group(2)).strip()
            if not url.startswith("http"):
                if url.startswith("/"): url = f"https://www.finanzamille.com{url}"
                else: url = f"https://www.finanzamille.com/{url}"
            if is_valid_fm_link(url) and url not in seen:
                seen.add(url)
                # filtra testi inutili
                if text.lower() in {"entra","accedi","scopri di più","newsletter gratuita"}: 
                    continue
                items.append({"title": text, "url": url})
            if len(items) >= limit:
                break
        if len(items) >= limit:
            break

    return jsonify(ok=True, count=len(items), items=items)

# ---- News scan (placeholder) --------------------------------
@app.get("/news/scan")
def news_scan():
    """
    Piccolo riassunto statico/placeholder. Param: region, window.
    Sostituire in seguito con provider news.
    """
    region = request.args.get("region","us")
    window = request.args.get("window","6h")
    bullets = [
        f"[{region.upper()}] Fed speakers in focus; rates sensitive sectors volatile",
        "Oil edges lower; USD mixed; mega-cap tech outperforms",
        "IG/HY credit stable; VIX subdued; gold flat",
    ]
    return jsonify(ok=True, region=region, window=window, headlines=bullets)

# ---- Portfolio CSV import -----------------------------------
@app.post("/portfolio/csv/import")
def portfolio_csv_import():
    """
    Accetta:
      - file multipart 'file' (CSV con header: ticker,qty,buy_price,buy_date,account)
      - oppure JSON: { 'csv_url': 'https://...' } (Drive/Dropbox pubblico)
    Ritorna parse + PnL grezzo (prezzi spot placeholder= None).
    """
    import csv, io

    def parse_csv(content: str):
        reader = csv.DictReader(io.StringIO(content))
        rows = []
        for r in reader:
            try:
                rows.append({
                    "ticker": r["ticker"].strip().upper(),
                    "qty": float(r["qty"]),
                    "buy_price": float(r["buy_price"]),
                    "buy_date": r.get("buy_date",""),
                    "account": r.get("account","ibkr"),
                })
            except Exception:
                continue
        return rows

    content = None
    if "file" in request.files:
        content = request.files["file"].read().decode("utf-8", errors="ignore")
    else:
        data = request.get_json(silent=True) or {}
        csv_url = data.get("csv_url")
        if csv_url:
            content = requests.get(csv_url, timeout=15).text

    if not content:
        return jsonify(ok=False, error="No CSV provided"), 400

    rows = parse_csv(content)

    # TODO prezzi spot: integrare provider (es. Alpaca/Polygon). Per ora None.
    for r in rows:
        r["spot"] = None
        r["pnl"] = None

    return jsonify(ok=True, positions=rows, count=len(rows))

# ---- Alpaca health (placeholder) ----------------------------
@app.get("/alpaca/health")
def alpaca_health():
    have_keys = bool(os.environ.get("ALPACA_API_KEY")) and bool(os.environ.get("ALPACA_SECRET_KEY"))
    return jsonify(ok=True, connected=have_keys)
