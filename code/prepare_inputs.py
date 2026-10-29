"""Convert the released CSVs into the input files the as-run pipeline scripts expect.

    python code/prepare_inputs.py

Writes, under code/data/:
    master_news_narrative.csv      stories + declined, columns used by run_phase1_narrator_judge.py
    master_news_narrative_v2.csv   same file under the name the sixw/ extractors look for
    master_summaries.csv           compression-0.55 summaries in the shape sixw/ expects
Requires code/data/master_articles_2000.csv (with body) from collect.py for any script that reads sources.
"""
import csv, os
csv.field_size_limit(10**9)
HERE = os.path.dirname(os.path.abspath(__file__))
REL = os.path.join(os.path.dirname(HERE), "data")
OUT = os.path.join(HERE, "data"); os.makedirs(OUT, exist_ok=True)

def rd(n):
    with open(os.path.join(REL, n), encoding="utf-8", newline="") as h: return list(csv.DictReader(h))

rows = []
# `stratum` is the internal batch label the as-run scripts filter on (cr_audit_source.py reads it).
def stratum(r): return "neutral_2026-07" if r["risk_level"] == "Neutral" else "initial_LMH"
for r in rd("outputs_story.csv"):
    rows.append(dict(gen_id=r["gen_id"], task="news_narrative", article_id=r["article_id"], url=r["url"],
                     gen_model_family=r["gen_model_family"], perspective=r["perspective"], is_possible="Y",
                     stratum=stratum(r), output_text=r["output_text"]))
for r in rd("outputs_declined.csv"):
    rows.append(dict(gen_id=r["gen_id"], task="news_narrative", article_id=r["article_id"], url=r["url"],
                     gen_model_family=r["gen_model_family"], perspective=r["perspective"], is_possible="N",
                     stratum=stratum(r), output_text=r["output_text"]))
p = os.path.join(OUT, "master_news_narrative.csv")
with open(p, "w", encoding="utf-8", newline="") as h:
    w = csv.DictWriter(h, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(f"wrote {p}: {len(rows)} rows")
import shutil; shutil.copy(p, os.path.join(OUT, "master_news_narrative_v2.csv"))

srows = []
for r in rd("outputs_summary.csv"):
    srows.append(dict(gen_id=r["gen_id"], article_id=r["article_id"], url=r["url"],
                      gen_model_family=r["gen_model_family"], compression_ratio=r["compression_ratio"],
                      refusal_flag=r["refusal_flag"], output_text=r["output_text"]))
p = os.path.join(OUT, "master_summaries.csv")
with open(p, "w", encoding="utf-8", newline="") as h:
    w = csv.DictWriter(h, fieldnames=list(srows[0])); w.writeheader(); w.writerows(srows)
print(f"wrote {p}: {len(srows)} rows")
