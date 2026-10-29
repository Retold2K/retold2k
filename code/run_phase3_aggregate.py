# -*- coding: utf-8 -*-
"""Phase 3 — 집계 (API 호출 없음).
입력: phase1/phase2 tier2.csv + data/master_judgments_summary.csv(기존 요약 판정)
출력: phase3_aggregate/
  activation_by_task.csv      H1: 태스크 x code_group 검출률 (narrator는 total/unlicensed 분리, judge 비집계 병기)
  blame_shift.csv             H2: perspective x valence x target_role
  per_judge_disagreement.csv  H3 재료: 아이템별 judge 불일치
  length_norm.csv             단어 100당 검출률
  report.md                   요약 리포트
"""
import os, sys
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "phase3_aggregate")
os.makedirs(OUT, exist_ok=True)
RESP = {"RI", "AR", "CD"}


def code_group(c):
    return "responsibility" if c in RESP else "surface"


def load_tier2(path):
    d = pd.read_csv(path, sep="|")
    d["code_group"] = d["distortion_code"].map(code_group)
    return d


def main():
    p1 = load_tier2(os.path.join(HERE, "phase1_narrator_judge", "tier2.csv"))
    rows = []
    # narrator: total / unlicensed
    for label, sub in [("narrator_total", p1[p1.detected == 1]),
                       ("narrator_unlicensed", p1[(p1.detected == 1) & (p1.licensed.astype(str) == "0")])]:
        base = len(p1) / 6  # 판정 단위 수
        for (grp, code), n in sub.groupby(["code_group", "distortion_code"]).size().items():
            rows.append([label, grp, code, n, round(100 * n / base, 3)])
    # phase2 통제
    p2p = os.path.join(HERE, "phase2_instrument_control", "tier2.csv")
    if os.path.exists(p2p):
        p2 = load_tier2(p2p)
        base2 = len(p2) / 6
        for (grp, code), n in p2[p2.detected == 1].groupby(["code_group", "distortion_code"]).size().items():
            rows.append(["summary_control(narr-prompt)", grp, code, n, round(100 * n / base2, 3)])
    # 기존 요약 판정 (원 프롬프트, cr=0.55)
    js = pd.read_csv(os.path.join(HERE, "data", "master_judgments_summary.csv"))
    js = js[js["compression_ratio"] == 0.55]
    basej = len(js) / 6
    for (grp, code), n in js[js.detected == 1].groupby(["code_group", "distortion_code"]).size().items():
        rows.append(["summary_orig(cr0.55)", grp, code, n, round(100 * n / basej, 3)])
    pd.DataFrame(rows, columns=["arm", "code_group", "code", "n_detected", "rate_pct"]).to_csv(
        os.path.join(OUT, "activation_by_task.csv"), index=False)

    # judge 비집계 (다수결로 합치지 않음)
    pj = (p1[p1.detected == 1].groupby(["judge_model", "code_group"]).size()
          .unstack(fill_value=0))
    pj.to_csv(os.path.join(OUT, "activation_per_judge.csv"))

    # H2 blame shift
    det = p1[p1.detected == 1]
    bs = (det.groupby(["perspective", "valence", "target_role"]).size()
             .rename("n").reset_index())
    bs.to_csv(os.path.join(OUT, "blame_shift.csv"), index=False)

    # H3 재료: 아이템x코드별 judge 불일치
    piv = p1.pivot_table(index=["item_id", "distortion_code", "code_group",
                                "perspective", "region", "risk_level"],
                         columns="judge_model", values="detected", aggfunc="first")
    piv = piv.dropna()
    if piv.shape[1] >= 2:
        piv["disagree"] = (piv.nunique(axis=1) > 1).astype(int)
        piv.reset_index().to_csv(os.path.join(OUT, "per_judge_disagreement.csv"), index=False)
        dis = piv.reset_index().groupby("code_group")["disagree"].mean()
    else:
        dis = pd.Series(dtype=float)

    # 길이 정규화 (검출 기회 통제)
    arts = pd.read_csv(os.path.join(HERE, "data", "master_articles_2000.csv"))
    wl = arts.set_index("url")["body"].astype(str).str.split().str.len()
    det2 = det.copy()
    det2["src_words"] = det2["url"].map(wl)
    ln = (det2.groupby("code_group").apply(
        lambda g: 100.0 * len(g) / g["src_words"].sum()).rename("det_per_100_src_words"))
    ln.to_csv(os.path.join(OUT, "length_norm.csv"))

    # 리포트
    L = ["# Phase3 리포트", ""]
    L.append(f"- phase1 판정 단위: {int(len(p1)/6)} (행 {len(p1)})")
    un = p1[(p1.detected == 1) & (p1.licensed.astype(str) == "0")]
    L.append(f"- narrator detected 총 {int((p1.detected==1).sum())} / unlicensed {len(un)}")
    L.append(f"- narrator responsibility(unlicensed): "
             f"{un[un.code_group=='responsibility'].groupby('distortion_code').size().to_dict()}")
    L.append(f"- 요약(원 프롬프트, 0.55) responsibility: "
             f"{js[(js.detected==1)&(js.distortion_code.isin(RESP))].groupby('distortion_code').size().to_dict()}")
    if os.path.exists(p2p):
        L.append(f"- 통제군(요약+narr프롬프트) responsibility detected: "
                 f"{int(((p2.detected==1)&(p2.code_group=='responsibility')).sum())}")
    if len(dis):
        L.append(f"- judge 불일치율 by code_group: {dis.round(3).to_dict()}")
    open(os.path.join(OUT, "report.md"), "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
