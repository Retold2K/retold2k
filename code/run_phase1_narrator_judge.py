# -*- coding: utf-8 -*-
"""Phase 1 — narrator 1,445건 x 2 cross-judge = 2,890콜.
출력: phase1_narrator_judge/tier2.csv (재개형)
사용: python run_phase1_narrator_judge.py [--budget N] [--smoke K]
"""
import os, sys, argparse
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common_utils import make_client
from judge_core import run_judging


def load_items(smoke=0):
    arts = pd.read_csv(os.path.join(HERE, "data", "master_articles_2000.csv"))
    narr = pd.read_csv(os.path.join(HERE, "data", "master_news_narrative.csv"))
    narr = narr[narr["is_possible"] == "Y"].merge(
        arts[["url", "body", "risk_level", "region"]], on="url", how="left")
    narr = narr[narr["body"].notna() & narr["output_text"].notna()]
    items = []
    for _, r in narr.iterrows():
        items.append(dict(
            item_id=r["gen_id"], url=r["url"], task="news_narrative",
            gen_model_family=r["gen_model_family"], perspective=r["perspective"],
            risk_level=r["risk_level"], region=r["region"], compression_ratio="",
            source_body=r["body"], output_text=r["output_text"]))
    if smoke:
        # 관점 다양성 우선 스모크
        pri = [x for x in items if x["perspective"] in ("Perpetrator", "Victim", "Survivor")]
        rest = [x for x in items if x not in pri]
        items = pri[: smoke // 2] + rest[: smoke - smoke // 2]
    return items


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=10**9)
    ap.add_argument("--smoke", type=int, default=0, help="스모크 아이템 수 (0=전량)")
    a = ap.parse_args()
    items = load_items(a.smoke)
    print(f"items={len(items)} -> expected calls ~{len(items)*2}")
    run_judging(items, os.path.join(HERE, "phase1_narrator_judge"),
                make_client, budget_calls=a.budget)
