import os, io, csv, re, requests, datetime as dt
from flask import Flask, request, jsonify

app = Flask(__name__)

# ---------- UTILS ----------
def now_iso():
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def ok(data=None, **extra):
    base = {"ok": True, "timestamp": now_iso()}
    if data:
        base.update(data)
    base.update(extra)
    return jsonify(base), 200

def err(msg, code=400):
    return jsonify({"ok": False, "error": msg}), code

# ---------- HEALTH ----------
@app.get("/health")
def health():
    return ok({"service": "investment-sentinel-api"})

# ---------- FINANZAMILLE ----------
@app.get("/finanzamille/digest")
def finanzamille_digest():
    limit = int(request.args.get("limit", 5))
    seeds = [
        "https://www.finanzamille.com/daily-news",
        "https://www.finanzamille.com"
    ]
    items, seen = [], set()
    headers = {"User-Agent": "Mozilla/5.0"}

    for seed in seeds:
        try:
            html = requests.get(seed, headers=headers, timeout=12).text
        except Exception:
            continue
        for m in re.finditer(r'href="([^"]+)"[^>]*>([^<]{3,120})</a>', html):
            url, title = m.group(1), re.sub(r"\s+", " ", m.group(2)).strip()
            if not url.startswith("http"):
                if url.startswith("/"): url = f"https://www.finanzamille.com{url}"
                else: url = f"https://www.finanzamille.com/{url}"
            if "blog-2-1" not in url or url in seen:
                continue
            seen.add(url)
            items.append({"title": title, "url": url})
            if len(items) >= limit:
                break
        if len(items) >= limit:
            break
    return ok({"count": len(items), "items": items})

# ---------- NEWS SCAN ----------
@app.get("/news/scan")
def news_scan():
    region = request.args.get("region", "us")
    window = request.args.get("window", "6h")
    sample = [
        f"[{region.upper()}] Fed speakers in focus, volatility low",
        "Oil dips slightly, gold steady, USD mixed",
        "Tech leads equities rebound; yields stable"
    ]
    return ok({"region": region, "window": window, "headlines": sample})

# ---------- PORTFOLIO CSV IMPORT ----------
@app.post("/portfolio/csv/import")
def portfolio_csv_import():
    import io, csv
    if "file" in request.files:
        content = request.files["file"].read().decode("utf-8", errors="ignore")
    else:
        data = request.get_json(silent=True) or {}
        csv_url = data.get("csv_url")
        if not csv_url:
            return err("No CSV provided")
        content = requests.get(csv_url, timeout=15).text

    reader = csv.DictReader(io.StringIO(content))
    rows = []
    for r in reader:
        try:
            rows.append({
                "ticker": r["ticker"].upper(),
                "qty": float(r["qty"]),
                "buy_price": float(r["buy_price"]),
                "buy_date": r.get("buy_date", ""),
                "account": r.get("account", "ibkr"),
                "spot": None,
                "pnl": None
            })
        except Exception:
            continue
    return ok({"positions": rows, "count": len(rows)})

# ---------- ALPACA HEALTH ----------
@app.get("/alpaca/health")
def alpaca_health():
    connected = bool(os.environ.get("ALPACA_API_KEY"))
    return ok({"connected": connected})

# ---------- MAIN ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
