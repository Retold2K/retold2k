"""Fill contrib/cr_audit_per_story.csv: contradiction-rate audit of every story.

Uses the prompt, model and parser from prompts/cr_audit_source.py unchanged
(imported, not copied), so results are comparable with the paper's audit.

    export ANTHROPIC_API_KEY=...
    python collect.py                    # bodies are needed
    python contrib/run_cr_audit_all.py [--limit N] [--sleep 0.2]

Resumable: rows that already have total_claims are skipped.
"""
import argparse, csv, importlib.util, json, os, sys, time
from datetime import datetime, timezone

csv.field_size_limit(10**9)
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
TEMPLATE = os.path.join(HERE, "cr_audit_per_story.csv")
ARTS = os.path.join(ROOT, "code", "data", "master_articles_2000.csv")

spec = importlib.util.spec_from_file_location("cr_audit_source", os.path.join(ROOT, "prompts", "cr_audit_source.py"))
src = importlib.util.module_from_spec(spec); spec.loader.exec_module(src)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0); ap.add_argument("--sleep", type=float, default=0.2)
    a = ap.parse_args()
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key: raise SystemExit("set ANTHROPIC_API_KEY")
    if not os.path.exists(ARTS): raise SystemExit(f"{ARTS} missing: run collect.py first")
    arts = {}
    with open(ARTS, encoding="utf-8", newline="") as h:
        for r in csv.DictReader(h): arts[r["article_id"]] = (r.get("title", ""), r.get("body", ""))
    stories = {}
    with open(os.path.join(ROOT, "data", "outputs_story.csv"), encoding="utf-8", newline="") as h:
        for r in csv.DictReader(h): stories[r["gen_id"]] = r["output_text"]
    with open(TEMPLATE, encoding="utf-8", newline="") as h:
        rows = list(csv.DictReader(h)); cols = list(rows[0])
    n = 0
    for r in rows:
        if r["total_claims"] != "": continue
        if a.limit and n >= a.limit: break
        title, body = arts.get(r["article_id"], ("", ""))
        if not body: continue
        try:
            res = src.call(key, title, body, stories[r["gen_id"]])
        except Exception as e:
            print(f"[err] {r['gen_id']}: {e}", file=sys.stderr); continue
        tc = int(res.get("total_claims") or 0); cc = int(res.get("contradicted_claims") or 0)
        r.update(audit_model=src.MODEL, total_claims=tc, contradicted_claims=cc,
                 cr_claim=f"{(cc / tc) if tc else 0.0:.6f}",
                 contradiction_examples=json.dumps(res.get("contradiction_examples") or [], ensure_ascii=False)[:500],
                 cr_zero=1 if (tc and cc == 0) else 0,
                 audited_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        n += 1
        if n % 25 == 0:
            with open(TEMPLATE, "w", encoding="utf-8", newline="") as h:
                w = csv.DictWriter(h, fieldnames=cols); w.writeheader(); w.writerows(rows)
            print(f"  {n} audited", file=sys.stderr)
        time.sleep(a.sleep)
    with open(TEMPLATE, "w", encoding="utf-8", newline="") as h:
        w = csv.DictWriter(h, fieldnames=cols); w.writeheader(); w.writerows(rows)
    print(f"done: {n} new rows. cr_zero rows = contradiction-free stories (the paper's blind-spot denominator).")

if __name__ == "__main__":
    main()
