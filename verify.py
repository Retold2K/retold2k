"""Integrity checks for the ReTold-2k release bundle.

Run from the release root:  python verify.py
Every number asserted here is the number printed in the paper
(TAE @ NeurIPS 2026 camera-ready). If an assertion fails, the bundle
and the paper disagree and one of them must be fixed before upload.
"""
import csv, os, re, sys
from collections import Counter, defaultdict

csv.field_size_limit(10**9)
HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data")

def rd(name):
    with open(os.path.join(D, name), encoding="utf-8", newline="") as h:
        return list(csv.DictReader(h))

fails = []
def check(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond: fails.append(msg)

A  = rd("articles_index.csv")
S  = rd("outputs_story.csv")
Dc = rd("outputs_declined.csv")
Su = rd("outputs_summary.csv")
J  = rd("judgments.csv")
C  = rd("contested_911.csv")
L  = rd("author_labels_50.csv")

# ---- row counts (Table 7 and Section 3) ----
check(len(A)  == 1999,  f"articles_index rows = {len(A)} (expect 1999)")
check(len(S)  == 1926,  f"outputs_story rows = {len(S)} (expect 1926)")
check(len(Dc) == 73,    f"outputs_declined rows = {len(Dc)} (expect 73)")
check(len(Su) == 5984,  f"outputs_summary rows = {len(Su)} (expect 5984)")
check(len(J)  == 94812, f"judgments rows = {len(J)} (expect 94812 = 23094 story + 71718 summary)")
check(len(L)  == 150,   f"author_labels_50 rows = {len(L)} (expect 150 = 50 items x 3 annotators)")
pairs_c = {(r["item_id"], r["distortion_code"]) for r in C}
check(len(pairs_c) == 911, f"contested judgments (story, code) = {len(pairs_c)} (expect 911)")
check(len({r["item_id"] for r in C}) == 700, "contested judgments span 700 distinct stories")
check(len(C) == 1822, f"contested rows = {len(C)} (expect 1822 = 911 x 2 judges)")

# ---- no article body anywhere ----
for name, rows in [("articles_index", A), ("outputs_story", S), ("outputs_declined", Dc),
                   ("outputs_summary", Su), ("judgments", J), ("contested_911", C), ("author_labels_50", L)]:
    check("body" not in rows[0], f"{name}: no 'body' column")

# ---- article coverage ----
aid = {a["article_id"] for a in A}
check(len(aid) == len(A), "article_id unique")
check(all(a["url"].startswith("http") for a in A), "every article has a URL")
check({s["article_id"] for s in S} | {d["article_id"] for d in Dc} == aid, "story + declined article ids == articles_index")
check(len({s["article_id"] for s in S} & {d["article_id"] for d in Dc}) == 0, "no article both story and declined")
check({s["article_id"] for s in Su} <= aid, "summary article ids subset of articles_index")

# ---- story/summary judgments ----
Js = [j for j in J if j["task"] == "story"]
Jm = [j for j in J if j["task"] == "summary"]
check(len(Js) == 23094, f"story judgment rows = {len(Js)} (expect 23094)")
check(len(Jm) == 71718, f"summary judgment rows = {len(Jm)} (expect 71718)")
key = Counter((j["item_id"], j["distortion_code"], j["judge_model"]) for j in J)
check(max(key.values()) == 1, "(item_id, distortion_code, judge_model) unique in judgments")
check(set(j["distortion_code"] for j in J) == {"AR","RI","AS","CD","SO","IJ"}, "six distortion codes only")
per_item = Counter(j["item_id"] for j in Js)
check(Counter(per_item.values()) == Counter({12: 1923, 6: 3}),
      "1923 stories have 6 codes x 2 judges; 3 Claude stories have only the GPT judge (Gemini judge call failed; see README)")
check(len(per_item) == 1926, "story judgments cover all 1926 stories")
check(set(j["judge_model"] for j in J) <= {"gpt","gemini","claude"}, "judge families")
gen_judge = [(j["gen_model_family"], j["judge_model"]) for j in Js]
check(all(g != jm for g, jm in gen_judge), "leave-one-generator-out: judge never equals generator")
check(all(j["licensed"] in ("0","na") for j in Jm), "summary rows never licensed=1")

# ---- paper Table 2 numbers: story rows, consensus detection ----
# consensus = both judges detected=1 AND both licensed=0 (unwarranted)
by_item = defaultdict(dict)
for j in Js:
    by_item[(j["item_id"], j["distortion_code"])][j["judge_model"]] = (j["detected"], j["licensed"])
cons = Counter(); any_ = Counter()
for (iid, code), d in by_item.items():
    vals = list(d.values())
    if len(vals) == 2:
        if all(v == ("1","0") for v in vals): cons[code] += 1
        if any(v == ("1","0") for v in vals): any_[code] += 1
print("     consensus unwarranted detections per code:", dict(cons))

# ---- contested set: AR/RI/CD where two judges' (detected, licensed) differ ----
check(set(c["distortion_code"] for c in C) <= {"AR","RI","CD"}, "contested set limited to accountability codes")
cc = Counter((c["item_id"], c["distortion_code"]) for c in C)
check(set(cc.values()) == {2}, "contested: exactly 2 judge rows per (item, code)")
check(all("output_text" in c and c["output_text"] for c in C), "contested rows carry output_text")

# ---- refusals (Section 5 / Table 6) ----
rc = Counter(d["reason_label"] for d in Dc)
print("     refusal reasons:", dict(rc))
check(Counter(d["gen_model_family"] for d in Dc) == Counter({"claude":71,"gpt":2}), "refusals by family = claude 71, gpt 2, gemini 0")

# ---- author labels (Section 5, Appendix) ----
check(set(l["annotator"] for l in L) == {"A1","A2","A3"}, "annotators are A1,A2,A3 (no real names)")
check(set(l["label"] for l in L) <= {"1","0","-1",""}, "labels in {1,0,-1,blank}")
lc = {a: Counter(l["label"] for l in L if l["annotator"]==a) for a in ("A1","A2","A3")}
check(lc["A1"]["1"]==26 and lc["A2"]["1"]==10 and lc["A3"]["1"]==9, "per-annotator label=1 counts 26/10/9")
pairs_l = {(l["item_id"], l["distortion_code"]) for l in L}
check(len(pairs_l) == 50, "50 distinct labelled (story, code) judgments")
check(pairs_l <= pairs_c, "labelled judgments drawn from the contested set")
check(Counter(l["kind"] for l in L) == Counter({"detection_split": 96, "legitimacy_split": 54}), "32 detection-split + 18 legitimacy-split items (x3 annotators)")

# ---- PII / secrets scan on text columns ----
pat = re.compile(r"(sk-ant-[A-Za-z0-9_\-]{20,}|AIza[0-9A-Za-z_\-]{30,}|sk-[A-Za-z0-9]{32,})")
hit = 0
for rows in (S, Dc, Su, C):
    for r in rows:
        if pat.search(r.get("output_text","")): hit += 1
check(hit == 0, "no API-key-like strings in output_text")
names = re.compile(r"박광석|양지웅|세냐|Senya|kspark")
check(not any(names.search(l["note"]) for l in L), "no annotator real names in notes")

# ---- contrib slots (python verify.py --contrib) ----
if "--contrib" in sys.argv:
    CD = os.path.join(HERE, "contrib")
    def rdc(name):
        with open(os.path.join(CD, name), encoding="utf-8", newline="") as h:
            return list(csv.DictReader(h))
    jm = rdc("judgments_missing.csv")
    check(len(jm) == 264 and list(jm[0]) == list(J[0]) + ["reason"], "judgments_missing: 264 rows, judgments columns + reason")
    check(not ({(r["item_id"], r["distortion_code"], r["judge_model"]) for r in jm} & key.keys()), "judgments_missing: no overlap with judgments.csv")
    filled = [r for r in jm if r["detected"] != ""]
    check(all(r["detected"] in ("0","1") and r["licensed"] in ("0","1","na") for r in filled), f"judgments_missing: {len(filled)} filled rows have valid detected/licensed")
    sm = rdc("outputs_summary_missing.csv")
    check(len(sm) == 13 and set(r["status"] for r in sm) <= {"generated_not_judged","to_generate","generated"}, "outputs_summary_missing: 13 rows, valid status")
    cr = rdc("cr_audit_per_story.csv")
    check({r["gen_id"] for r in cr} == {s["gen_id"] for s in S}, "cr_audit_per_story: keyed on every story")
    done = [r for r in cr if r["total_claims"] != ""]
    check(all(r["total_claims"].isdigit() and r["contradicted_claims"].isdigit() and r["cr_zero"] in ("0","1") for r in done), f"cr_audit_per_story: {len(done)} audited rows well-formed")
    lt = rdc("labels_template.csv")
    check(len(lt) == 911 and {(r["item_id"], r["distortion_code"]) for r in lt} == pairs_c, "labels_template: the 911 contested judgments")
    lab = [r for r in lt if r["label"] != ""]
    check(all(r["label"] in ("1","0","-1") and re.fullmatch(r"A\d+", r["annotator"] or "") for r in lab), f"labels_template: {len(lab)} labelled rows use codes A<n> and labels in {{1,0,-1}}")
    for name in ["judgments_missing.csv","outputs_summary_missing.csv","cr_audit_per_story.csv","labels_template.csv","url_alternates.csv"]:
        rows = rdc(name)
        check("body" not in rows[0], f"{name}: no body column")
        check(all(len(v) <= 12000 for r in rows for k, v in r.items() if k != "output_text"), f"{name}: no oversized cells")

print()
print("ALL CHECKS PASSED" if not fails else f"{len(fails)} CHECK(S) FAILED")
sys.exit(1 if fails else 0)
