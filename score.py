"""Reproduce the paper's numbers from the released files, and score a detector.

    python score.py                      # reproduce Tables 4, 5, A1, A2, licensing share, refusals
    python score.py --detector my.csv    # score your detector against each judge separately

Standard library only. Definitions used throughout:

  unwarranted detection : detected == 1 and licensed == 0 (per judge, per code)
  accountability codes  : AR, RI, CD      surface codes : AS, SO, IJ
  paired set            : the 1,923 articles whose story and whose compression-0.55
                          summary come from the same model family
  mean +- s.d.          : over the three judge families (sample s.d., n = 3)

A detector file has one row per (item_id, distortion_code) with a column
`detected` in {0,1}; optionally `licensed` in {0,1,na}. It is scored
against each judge family separately, never against a merged gold label,
because the paper argues no such label exists for the contested cases.
"""
import argparse, csv, os, statistics as st
from collections import Counter, defaultdict
from math import comb, sqrt

csv.field_size_limit(10**9)
HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data")
RESP = {"AR", "RI", "CD"}
CODES = ["AR", "CD", "RI", "AS", "SO", "IJ"]
NAMES = {"AR": "Vanishing Actor", "CD": "Causal Fading", "RI": "Role Reversal",
         "AS": "Claim Laundering", "SO": "Selective Omission", "IJ": "Invented Addition"}
JUDGES = ["gpt", "gemini", "claude"]
GROUP = {"Neutral Observer": "Third-party observers and helpers", "Rescuer": "Third-party observers and helpers",
         "Neighbor": "Third-party observers and helpers", "Historian": "Third-party observers and helpers",
         "Witness": "Third-party observers and helpers", "Perpetrator": "Perpetrator",
         "Victim": "Victim side", "Survivor": "Victim side", "Descendant": "Victim side",
         "Bereaved family": "Victim side", "Journalist": "Professional accountability roles",
         "Investigator": "Professional accountability roles"}

def rd(name):
    with open(os.path.join(D, name), encoding="utf-8", newline="") as h:
        return list(csv.DictReader(h))

def unwarranted(j): return j["detected"] == "1" and j["licensed"] == "0"
def detected(j):    return j["detected"] == "1"

def mcnemar_exact(b, c):
    n = b + c
    if n == 0: return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)

def binom_two_sided(k, n):
    return min(1.0, 2 * sum(comb(n, i) for i in range(min(k, n - k) + 1)) / 2 ** n)

def per_judge(rows, cond):
    """rate per judge for each code -> {code: (mean, sd)}"""
    out = {}
    for code in CODES:
        per = []
        for jm in JUDGES:
            r = [x for x in rows if x["judge_model"] == jm and x["distortion_code"] == code]
            per.append(100 * sum(cond(x) for x in r) / len(r))
        out[code] = (st.mean(per), st.stdev(per))
    return out

def main_tables():
    J = rd("judgments.csv")
    Js = [j for j in J if j["task"] == "story"]
    Jm = [j for j in J if j["task"] == "summary"]
    S = rd("outputs_story.csv")
    Dc = rd("outputs_declined.csv")
    fam = {s["article_id"]: s["gen_model_family"] for s in S}
    sev = {s["article_id"]: s["risk_level"] for s in S}
    pair = {(j["article_id"], j["gen_model_family"]) for j in Jm if fam.get(j["article_id"]) == j["gen_model_family"]}
    Jp = [j for j in Jm if (j["article_id"], j["gen_model_family"]) in pair]
    arts = sorted({a for a, _ in pair})
    print(f"stories {len({j['item_id'] for j in Js})}, story judgment rows {len(Js)}, "
          f"summary judgment rows {len(Jm)}, paired articles {len(arts)}\n")

    # ---- Table A1 / Figure 2 ----
    print("Table A1. Detection rates by task (%, mean +- s.d. over three judges)")
    print(f"{'Type':20s} {'Summary':>14s} {'Story unwarranted':>20s} {'Story all':>14s}")
    sm = per_judge(Jp, detected); su = per_judge(Js, unwarranted); sa = per_judge(Js, detected)
    for c in CODES:
        print(f"{NAMES[c]:20s} {sm[c][0]:6.1f} +- {sm[c][1]:4.1f} {su[c][0]:12.1f} +- {su[c][1]:4.1f} {sa[c][0]:6.1f} +- {sa[c][1]:4.1f}")

    # ---- licensing share ----
    det = [j for j in Js if detected(j)]
    print(f"\nShare of story detections judged warranted: {100*sum(j['licensed']=='1' for j in det)/len(det):.1f}%")
    for c in ["SO", "IJ", "AR", "AS", "CD", "RI"]:
        d = [j for j in det if j["distortion_code"] == c]
        print(f"   {NAMES[c]:20s} {100*sum(j['licensed']=='1' for j in d)/len(d):5.1f}%  (of {len(d)} detections)")

    # ---- Table 4: paired comparison by severity (article level, accountability codes) ----
    sj = defaultdict(set); mj = defaultdict(set)
    for j in Js:
        if j["distortion_code"] in RESP and unwarranted(j): sj[j["article_id"]].add(j["judge_model"])
    for j in Jp:
        if j["distortion_code"] in RESP and detected(j): mj[j["article_id"]].add(j["judge_model"])
    print("\nTable 4. Paired comparison by topic severity (% of articles with an unwarranted accountability distortion)")
    print(f"{'':10s} {'n':>5s} {'Story':>7s} {'Both':>6s} {'Summary':>8s} {'McNemar p':>11s}")
    B = C_ = 0
    for lvl in ["Neutral", "Low", "Medium", "High"]:
        A = [a for a in arts if sev.get(a) == lvl]
        s1 = sum(1 for a in A if sj[a]); s2 = sum(1 for a in A if len(sj[a]) >= 2); m1 = sum(1 for a in A if mj[a])
        b = sum(1 for a in A if sj[a] and not mj[a]); c = sum(1 for a in A if mj[a] and not sj[a]); B += b; C_ += c
        print(f"{lvl:10s} {len(A):5d} {100*s1/len(A):7.1f} {100*s2/len(A):6.1f} {100*m1/len(A):8.1f} {mcnemar_exact(b,c):11.1e}")
    print(f"articles on which the tasks differ: {B+C_}, stories only: {B}, summaries only: {C_}, p = {mcnemar_exact(B,C_):.1e}")

    # ---- Table 5: judge disagreement by whether the perpetrator is implicated ----
    by = defaultdict(dict)
    for j in Js: by[(j["item_id"], j["distortion_code"])][j["judge_model"]] = j
    pairs = [frozenset(p) for p in [("gpt", "gemini"), ("gpt", "claude"), ("gemini", "claude")]]
    res = defaultdict(list)
    for grp in ["Accountability", "Surface"]:
        for pr in pairs:
            for role in ["perpetrator implicated", "otherwise"]:
                n = d = 0
                for (iid, code), dd in by.items():
                    if set(dd) != set(pr) or ((code in RESP) != (grp == "Accountability")): continue
                    r = "perpetrator implicated" if any(x["target_role"] == "perpetrator" for x in dd.values()) else "otherwise"
                    if r != role: continue
                    n += 1; d += len({x["detected"] for x in dd.values()}) > 1
                res[(grp, role)].append(100 * d / n)
    print("\nTable 5. Judge disagreement on detection (%, mean +- s.d. over three judge pairs)")
    for grp in ["Accountability", "Surface"]:
        a = res[(grp, "perpetrator implicated")]; o = res[(grp, "otherwise")]
        print(f"{grp:15s} perpetrator implicated {st.mean(a):5.1f} +- {st.stdev(a):4.1f}   otherwise {st.mean(o):5.1f} +- {st.stdev(o):4.1f}")

    # ---- Table A2 / Figure 3: direction toward the perpetrator ----
    pt = [j for j in Js if unwarranted(j) and j["distortion_code"] in RESP and j["target_role"] == "perpetrator"]
    mit = sum(j["valence"] == "mitigate" for j in pt); amp = sum(j["valence"] == "amplify" for j in pt)
    print(f"\nDirection. Perpetrator-targeted unwarranted accountability distortions: n = {len(pt)}, "
          f"mitigate {mit}, amplify {amp}, neutral {len(pt)-mit-amp}; "
          f"mitigation rate {100*mit/(mit+amp):.1f}% of {mit+amp} directional, binomial p = {binom_two_sided(amp, mit+amp):.1e}")
    g = defaultdict(Counter)
    for j in pt: g[GROUP[j["perspective"]]][j["valence"]] += 1
    print("Table A2. By narrator group (rate = mitigate / n, n includes neutral-valence rows, as in the paper)")
    for name, c in sorted(g.items(), key=lambda kv: -kv[1]["mitigate"] / sum(kv[1].values())):
        n = sum(c.values()); m = c["mitigate"]; a = c["amplify"]; p = m / n; se = sqrt(p * (1 - p) / n)
        print(f"   {name:36s} n={n:3d} mitigate={m:3d} amplify={a:3d} rate={p:.2f} ({max(0,p-1.96*se):.2f}-{min(1,p+1.96*se):.2f})")

    # ---- refusals ----
    print(f"\nDeclined requests: {len(Dc)}  by family {dict(Counter(d['gen_model_family'] for d in Dc))}  "
          f"by reason {dict(Counter(d['reason_label'] for d in Dc))}")

def score_detector(path):
    J = [j for j in rd("judgments.csv") if j["task"] == "story"]
    det = {}
    with open(path, encoding="utf-8", newline="") as h:
        for r in csv.DictReader(h):
            det[(r["item_id"], r["distortion_code"])] = r
    print(f"detector rows: {len(det)}")
    for jm in JUDGES:
        for grp, codes in [("accountability", RESP), ("surface", set(CODES) - RESP)]:
            tp = fp = fn = tn = 0
            for j in J:
                if j["judge_model"] != jm or j["distortion_code"] not in codes: continue
                r = det.get((j["item_id"], j["distortion_code"]))
                if r is None: continue
                ref = unwarranted(j); hyp = r["detected"] == "1" and r.get("licensed", "0") != "1"
                tp += ref and hyp; fp += hyp and not ref; fn += ref and not hyp; tn += (not ref) and (not hyp)
            if tp + fp + fn + tn == 0: continue
            P = tp / (tp + fp) if tp + fp else 0; R = tp / (tp + fn) if tp + fn else 0
            F = 2 * P * R / (P + R) if P + R else 0
            print(f"vs judge {jm:7s} {grp:15s} n={tp+fp+fn+tn:6d}  P={P:.3f} R={R:.3f} F1={F:.3f}")
    print("Report the three per-judge scores side by side; do not average them into one number.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--detector", help="CSV with item_id, distortion_code, detected[, licensed]")
    a = ap.parse_args()
    if a.detector: score_detector(a.detector)
    else: main_tables()
