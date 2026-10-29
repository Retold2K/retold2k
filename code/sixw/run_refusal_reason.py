# =============================================================
# run_refusal_reason.py — 거부 73건의 사유 규칙 분류 (API 불필요)
# 정보부족/정책/모호 3분류와 관찰(민감성 거부 vs 사실 불일치 거부)을 통합한 잠정 라벨.
# ⚠️ 규칙 기반 잠정 분류다. 마스터 병합 전 저자 확인 필수 (refusal_reason.csv를 눈으로 검수).
# 출력: sixw_out/refusal_reason.csv
# =============================================================
import os, csv, re

csv.field_size_limit(10**8)
ROOT = os.path.dirname(os.path.abspath(__file__))
def _find_data():
    for c in (os.path.join(ROOT,"data"), os.path.join(os.path.dirname(ROOT),"data")):
        if os.path.exists(os.path.join(c,"master_news_narrative_v2.csv")): return c
    return os.path.join(ROOT,"data")
DATA=_find_data(); OUT=os.path.join(ROOT,"sixw_out"); os.makedirs(OUT,exist_ok=True)

RULES = [  # (label, [cues]) — 위에서부터 첫 매치. cue는 소문자 비교.
 ("policy_safety",     ["i can't", "i cannot", "i won't", "unable to help", "harmful", "glorif",
                        "not appropriate", "cannot in good conscience", "victim", "perpetrat",
                        "traumat", "insensitive", "disrespect"]),
 ("no_such_narrative", ["no survivor", "no victim", "does not contain", "doesn't contain",
                        "no such", "not present in the article", "no clear", "lacks",
                        "there is no", "does not involve", "doesn't involve", "no casualties"]),
 ("insufficient_info", ["insufficient", "not enough detail", "too little", "lacks sufficient",
                        "limited information", "does not provide enough"]),
]

def classify(text):
    t = re.sub(r"\s+"," ", (text or "")).lower()
    for label, cues in RULES:
        for c in cues:
            if c in t: return label, c
    return "other_unclassified", ""

def main():
    src = os.path.join(DATA, "master_news_narrative_v2.csv")
    rows=[]
    with open(src, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r.get("is_possible") or "").strip().upper() != "N": continue
            label, cue = classify(r.get("output_text",""))
            rows.append({"gen_id": r.get("gen_id",""), "url": r["url"],
                         "gen_model_family": r.get("gen_model_family",""),
                         "perspective": r.get("perspective",""), "stratum": r.get("stratum",""),
                         "reason_label": label, "matched_cue": cue,
                         "refusal_excerpt": re.sub(r"\s+"," ", r.get("output_text",""))[:220]})
    out = os.path.join(OUT, "refusal_reason.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    from collections import Counter
    print(f"거부 {len(rows)}건 분류 → {out}")
    for (lab, st), n in sorted(Counter((r['reason_label'], r['stratum']) for r in rows).items()):
        print(f"  {lab:20s} {st:16s} {n}")
    print("⚠️ 잠정 라벨 — 저자 검수 후 master_news_narrative_v2에 병합할 것.")

if __name__ == "__main__":
    main()
