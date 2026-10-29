"""Rebuild the article corpus from data/articles_index.csv.

The article text is not distributed (copyright). This script fetches each
article's body from its URL and writes the file the pipeline scripts expect:

    code/data/master_articles_2000.csv   (articles_index columns + body)
    collect_log.csv                      one line per article: status, chars, source, timestamp

Two fetch routes, tried in order:

  1. Event Registry (newsapi.ai), the service the corpus was originally
     collected from. Set ER_API_KEY. Returns the same body text we used
     whenever the article is still indexed. Requires:  pip install eventregistry
  2. Direct fetch of the URL with trafilatura.  pip install trafilatura
     Returns whatever the page serves today; may differ from our copy
     (paywalls, edits, removed pages).

Usage:
    python collect.py                 # all articles, resumable
    python collect.py --limit 50      # smoke test
    python collect.py --no-er         # skip Event Registry

Re-run to resume: articles already in collect_log.csv with status "ok" are skipped.
Bodies that cannot be fetched by either route are logged as "failed"; the
pipeline treats missing bodies as missing articles. If your rebuilt corpus is
smaller than 1,999, say so when you report numbers.
"""
import argparse, csv, os, sys, time
from datetime import datetime, timezone

csv.field_size_limit(10**9)
HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "data", "articles_index.csv")
OUT_DIR = os.path.join(HERE, "code", "data")
OUT = os.path.join(OUT_DIR, "master_articles_2000.csv")
LOG = os.path.join(HERE, "collect_log.csv")
OUT_COLS = ["article_id", "url", "risk_level", "region", "minor_region", "concept",
            "minor_concept", "article_date", "title", "body"]

def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def fetch_er(er, mapper, url):
    """Event Registry: url -> article uri -> body."""
    from eventregistry import QueryArticle, RequestArticleInfo, ReturnInfo, ArticleInfoFlags
    uri = mapper.getArticleUri(url)
    if not uri: return None
    if isinstance(uri, list): uri = uri[0]
    q = QueryArticle(uri)
    q.setRequestedResult(RequestArticleInfo(ReturnInfo(articleInfo=ArticleInfoFlags(bodyLen=-1))))
    res = er.execQuery(q)
    info = (res or {}).get(uri, {}).get("info") or {}
    body = info.get("body")
    return body.strip() if body else None

def fetch_direct(url):
    import trafilatura
    html = trafilatura.fetch_url(url)
    if not html: return None
    txt = trafilatura.extract(html, include_comments=False, include_tables=False, favor_precision=True)
    return txt.strip() if txt else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-er", action="store_true")
    ap.add_argument("--sleep", type=float, default=0.5, help="seconds between direct fetches")
    a = ap.parse_args()

    er = mapper = None
    if not a.no_er:
        key = os.environ.get("ER_API_KEY")
        if key:
            try:
                from eventregistry import EventRegistry, ArticleMapper
                er = EventRegistry(apiKey=key, allowUseOfArchive=True)
                mapper = ArticleMapper(er)
            except ImportError:
                print("eventregistry not installed; falling back to direct fetch", file=sys.stderr)
        else:
            print("ER_API_KEY not set; using direct fetch only", file=sys.stderr)

    with open(INDEX, encoding="utf-8", newline="") as h:
        index = list(csv.DictReader(h))
    done = {}
    if os.path.exists(LOG):
        with open(LOG, encoding="utf-8", newline="") as h:
            for r in csv.DictReader(h): done[r["article_id"]] = r["status"]
    os.makedirs(OUT_DIR, exist_ok=True)
    new_out = not os.path.exists(OUT)
    fo = open(OUT, "a", encoding="utf-8", newline=""); wo = csv.DictWriter(fo, fieldnames=OUT_COLS)
    if new_out: wo.writeheader()
    new_log = not os.path.exists(LOG)
    fl = open(LOG, "a", encoding="utf-8", newline=""); wl = csv.writer(fl)
    if new_log: wl.writerow(["article_id", "url", "status", "route", "chars", "fetched_at", "error"])

    n = ok = 0
    for r in index:
        if done.get(r["article_id"]) == "ok": continue
        if a.limit and n >= a.limit: break
        n += 1
        body = route = None; err = ""
        if er is not None:
            try: body = fetch_er(er, mapper, r["url"]); route = "eventregistry" if body else None
            except Exception as e: err = f"er:{type(e).__name__}"
        if body is None:
            try:
                body = fetch_direct(r["url"]); route = "direct" if body else None
                time.sleep(a.sleep)
            except ImportError:
                err += " trafilatura-missing"; break
            except Exception as e: err += f" direct:{type(e).__name__}"
        if body:
            row = {c: r.get(c, "") for c in OUT_COLS}; row["body"] = body
            wo.writerow(row); ok += 1
            wl.writerow([r["article_id"], r["url"], "ok", route, len(body), now(), ""])
        else:
            wl.writerow([r["article_id"], r["url"], "failed", "", 0, now(), err.strip()])
        fo.flush(); fl.flush()
        if n % 50 == 0: print(f"{n} tried, {ok} ok", file=sys.stderr)
    fo.close(); fl.close()
    print(f"done: {n} tried, {ok} fetched. Log: {LOG}. Corpus: {OUT}")

if __name__ == "__main__":
    main()
