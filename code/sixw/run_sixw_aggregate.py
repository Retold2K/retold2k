# =============================================================
# run_sixw_aggregate.py — 육하원칙 축별 보존/창작 집계
# 2026-07-28. run_sixw_extract.py 산출물만 입력. API·심판 불필요.
#
# 무엇을 재는가 (모든 축 공통 두 지표)
#   보존율(retention)  = 원문 앵커 중 재생성물에 살아남은 비율      → "잃었는가"
#   창작율(novelty)    = 재생성물 앵커 중 원문에 없던 것의 비율     → "만들었는가"
# 두 지표를 분리하는 이유: 축마다 실패 양식이 다르다. 순수 손실(잃기만)과
# 대체(잃고 새로 짓기)는 같은 "왜곡률"로 뭉치면 구별되지 않는다.
#
# 축 정의 (앵커 = 비교 단위)
#   who   : SRL agent 명사구 (해로운 행위의 주체 여부는 6코드 판정이 담당, 여기선 존재)
#   whom  : SRL patient 명사구
#   what  : SRL predicate 표제어
#   why   : 인과쌍 (cue + effect 핵어)
#   source: 출처 표지의 source 명사구
#   when  : 시간 표현 — absolute(검증 가능) / relative(서사 시간) 분리 집계
#   where : 장소 개체 (GPE/LOC/FAC)
#
# 정규화: 표층 소문자화 + 관사/공백 정리 후 집합 비교(문자열 일치).
#   → 동일 지시대상의 다른 표현("the army"/"soldiers")은 못 잡는다. 과소 추정이며 보수적이다.
#   길이 보정: 100단어당 앵커 수를 함께 보고(서술이 짧아 덜 잡힌다는 반박 차단).
# 출력: sixw_out/agg_*.csv + SIXW_REPORT.md
# =============================================================
import os, csv, re, statistics as st
from collections import defaultdict

csv.field_size_limit(10**8)
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "sixw_out")
def _find_data():
    need = "master_articles_2000.csv"
    for cand in (os.path.join(ROOT, "data"), os.path.join(os.path.dirname(ROOT), "data")):
        if os.path.exists(os.path.join(cand, need)): return cand
    return os.path.join(ROOT, "data")
DATA = _find_data()
SEP = "|"

STOP_HEAD = re.compile(r"^(?:the|a|an|his|her|its|their|our|my|your|this|that|these|those)\s+", re.I)
def norm(s):
    s = re.sub(r"\s+", " ", (s or "")).strip().lower()
    s = STOP_HEAD.sub("", s)
    s = re.sub(r"[^\w\s:./-]", "", s)
    return s.strip()

def head(s):
    """구의 핵어 근사: 마지막 단어 (영어 명사구 기준)"""
    t = norm(s).split()
    return t[-1] if t else ""

def load(layer, name):
    p = os.path.join(OUT, f"{layer}_{name}.csv")
    if not os.path.exists(p): return []
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=SEP))

def wordcount_map():
    """길이 보정용 단어 수 (원문/요약/서술)"""
    wc = {"source": {}, "summary": {}, "narrative": {}}
    p = os.path.join(DATA, "master_articles_2000.csv")
    with open(p, encoding="utf-8") as f:
        for r in csv.DictReader(f): wc["source"][r["url"]] = len((r.get("body") or "").split())
    p = os.path.join(DATA, "master_summaries.csv")
    with open(p, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            k = f"{r['url']}::{r.get('gen_model_family','')}::{r.get('compression_ratio','')}"
            wc["summary"][k] = len((r.get("summary_text") or r.get("output_text") or "").split())
    for fn in ("master_news_narrative_v2.csv", "master_news_narrative.csv"):
        p = os.path.join(DATA, fn)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    k = r.get("gen_id") or f"{r['url']}::{r.get('perspective','')}"
                    wc["narrative"][k] = len((r.get("output_text") or "").split())
            break
    return wc

# ---------- 축별 앵커 집합 만들기 ----------
def anchors_by_url(layer):
    """반환: {url: {axis: set(anchor)}}, {key: url}, {key: {axis:set}}"""
    per_key = defaultdict(lambda: defaultdict(set))
    key_url = {}
    def put(rows, axis, fn):
        for r in rows:
            k = r["key"]; key_url[k] = r["url"]
            v = fn(r)
            if isinstance(v, (list, tuple)):
                for x in v:
                    if x: per_key[k][axis].add(x)
            elif v: per_key[k][axis].add(v)
    srl = load(layer, "srl")
    put(srl, "who",  lambda r: norm(r["agent"]))
    put(srl, "whom", lambda r: norm(r["patient"]))
    put(srl, "what", lambda r: norm(r["predicate"]))
    put(load(layer, "causal"), "why",
        lambda r: f'{norm(r["cue"])}>{head(r["effect"])}' if norm(r["cue"]) and head(r["effect"]) else "")
    put(load(layer, "attribution"), "source", lambda r: norm(r["source"]))
    tmp = load(layer, "temporal")
    put([r for r in tmp if r["kind"] == "absolute"], "when_abs", lambda r: norm(r["surface"]))
    put([r for r in tmp if r["kind"] == "relative"], "when_rel", lambda r: norm(r["surface"]))
    put(load(layer, "place"), "where", lambda r: norm(r["surface"]))
    man = load(layer, "manner")
    put([r for r in man if r["subtype"] == "instrument"], "how_instr",  lambda r: norm(r["surface"]))
    put([r for r in man if r["subtype"] == "means"],      "how_means",  lambda r: norm(r["surface"]))
    put([r for r in man if r["subtype"] == "manner"],     "how_manner", lambda r: norm(r["surface"]))
    return per_key, key_url

AXES = ["who", "whom", "what", "why", "source", "when_abs", "when_rel", "where",
        "how_instr", "how_means", "how_manner"]
AXIS_KO = {"who":"행위 주체", "whom":"행위 대상", "what":"행위(술어)", "why":"인과",
           "source":"출처", "when_abs":"시간(절대)", "when_rel":"시간(상대)", "where":"장소",
           "how_instr":"수단(도구)", "how_means":"수단(by -ing)", "how_manner":"방식(부사)"}

def main():
    wc = wordcount_map()
    src_key, src_ku = anchors_by_url("source")
    src_by_url = {src_ku[k]: v for k, v in src_key.items()}
    meta = {}
    with open(os.path.join(DATA, "master_articles_2000.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            meta[r["url"]] = {"rl": r["risk_level"], "region": r["region"]}

    results = defaultdict(list)   # (layer, axis) -> [(retention, novelty, url, key)]
    density = defaultdict(list)   # (layer, axis) -> 100단어당 앵커수
    for layer in ("summary", "narrative"):
        per_key, key_url = anchors_by_url(layer)
        for k, axes in per_key.items():
            u = key_url[k]
            if u not in src_by_url: continue
            for ax in AXES:
                S = src_by_url[u].get(ax, set()); G = axes.get(ax, set())
                w = wc[layer].get(k, 0)
                if w: density[(layer, ax)].append(100.0 * len(G) / w)
                if S:
                    results[(layer, ax)].append((len(S & G) / len(S),
                                                 (len(G - S) / len(G)) if G else 0.0, u, k))
    # 산출
    rows = []
    for ax in AXES:
        line = {"axis": ax, "axis_ko": AXIS_KO[ax]}
        for layer in ("summary", "narrative"):
            v = results[(layer, ax)]
            line[f"{layer}_n"] = len(v)
            line[f"{layer}_retention"] = round(100 * st.mean([x[0] for x in v]), 1) if v else None
            line[f"{layer}_novelty"]   = round(100 * st.mean([x[1] for x in v]), 1) if v else None
            d = density[(layer, ax)]
            line[f"{layer}_per100w"]   = round(st.mean(d), 2) if d else None
        rows.append(line)
    p = os.path.join(OUT, "agg_axis_overview.csv")
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

    # 층별 / 관점별 (서술만)
    for group, keyfn in (("stratum", lambda u, k: meta.get(u, {}).get("rl", "?")),
                         ("region",  lambda u, k: meta.get(u, {}).get("region", "?"))):
        out = []
        for ax in AXES:
            g = defaultdict(list)
            for ret, nov, u, k in results[("narrative", ax)]:
                g[keyfn(u, k)].append((ret, nov))
            for gk, v in sorted(g.items()):
                out.append({"axis": ax, group: gk, "n": len(v),
                            "retention": round(100 * st.mean([x[0] for x in v]), 1),
                            "novelty":   round(100 * st.mean([x[1] for x in v]), 1)})
        with open(os.path.join(OUT, f"agg_narrative_by_{group}.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["axis", group, "n", "retention", "novelty"]); w.writeheader(); w.writerows(out)

    # 리포트
    md = ["# 육하원칙 축별 보존·창작 집계 (자동 생성)", "",
          "보존율 = 원문 앵커 중 살아남은 비율 / 창작율 = 생성물 앵커 중 원문에 없던 비율. per100w = 100단어당 앵커 수(길이 보정).", ""]
    md.append("| 축 | 요약 보존 | 서술 보존 | 요약 창작 | 서술 창작 | 요약 밀도 | 서술 밀도 | n(요약/서술) |")
    md.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        md.append(f"| {r['axis_ko']}({r['axis']}) | {r['summary_retention']} | {r['narrative_retention']} | "
                  f"{r['summary_novelty']} | {r['narrative_novelty']} | {r['summary_per100w']} | "
                  f"{r['narrative_per100w']} | {r['summary_n']}/{r['narrative_n']} |")
    md += ["", "해석 규칙 (대장 준수)", "- 문자열 일치 기반이라 동일 지시대상의 다른 표현을 놓친다: 보존율은 과소, 창작율은 과대 추정될 수 있다.",
           "- 상대 시간(when_rel)의 창작은 서사에서 정당할 수 있다 — 정당성 판정 없이 왜곡이라 부르지 않는다.",
           "- 축별 비교는 같은 파이프라인·같은 짝지은 기사 기준이므로 층위 간 대조는 유효하다."]
    open(os.path.join(OUT, "SIXW_REPORT.md"), "w", encoding="utf-8").write("\n".join(md))
    print("\n".join(md))
    print(f"\n저장: {p}, agg_narrative_by_stratum.csv, agg_narrative_by_region.csv, SIXW_REPORT.md")

if __name__ == "__main__":
    main()
