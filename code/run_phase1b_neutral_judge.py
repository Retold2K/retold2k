# -*- coding: utf-8 -*-
"""Phase 1b — Neutral 신규 관점 서술의 6-code 판정 (Phase 1과 동일 규약).
입력: phase0b_neutral_generation/neutral_narratives.csv (is_possible=='Y'만)
심판: leave-one-family-out 2개, SYS_JUDGE_NARR, 재개형(progress.txt).
출력: phase1b_neutral_judge/tier2.csv (Phase1과 동일 HEADER)
스모크: SMOKE=1 → 판정 12콜만.
"""
import os, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common_utils import ROOT, make_client
from judge_core import run_judging
import pandas as pd

def main():
    smoke = os.environ.get("SMOKE") == "1"
    gen_path = os.path.join(ROOT, "phase0b_neutral_generation", "neutral_narratives.csv")
    nn = pd.read_csv(gen_path, sep="|")
    nn = nn[nn.is_possible == "Y"].copy()
    a = pd.read_csv(os.path.join(ROOT, "data", "master_articles_2000.csv"))
    a = a[["article_id", "url", "region", "risk_level", "title", "body"]]
    m = nn.merge(a, on=["article_id", "url"], how="left")
    print(f"판정 대상(Y): {len(m)} → 예상 콜 {len(m)*2}")

    items = []
    for _, r in m.iterrows():
        items.append(dict(
            item_id=r["gen_id"], url=r["url"], task="news_narrative_neutral",
            gen_model_family=r["gen_model_family"], perspective=r["perspective"],
            risk_level="Neutral", region=r["region"], compression_ratio="",
            source_body=str(r["title"]) + "\n\n" + str(r["body"]),
            output_text=r["output_text"]))
    budget = 12 if smoke else 10**9
    run_judging(items, os.path.join(ROOT, "phase1b_neutral_judge"),
                make_client, budget_calls=budget)

if __name__ == "__main__":
    main()
