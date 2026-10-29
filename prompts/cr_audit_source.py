# =============================================================
# run_cr_neutral.py — 중립층 관점 서술 481건의 claim CR 측정 (Anthropic API 필요)
# 2026-07-28. 목적: master_cr_claims.csv(1,445 = 초기층)의 공백인 중립층을 메운다.
# **프롬프트·모델·판정 규약은 원본 run_table2_cr_v2.py(2026-04-25)와 문자 그대로 동일** —
# 다르면 기존 1,445건과 비교 불가이므로 절대 수정 금지. 입력만 마스터 v2의 중립층으로 바꿈.
# 재개형: 출력 CSV에 있는 gen_id는 건너뜀.
# 실행: python run_cr_neutral.py --keys ../keys.txt   (상위 폴더 keys.txt의 claude 키 사용)
# =============================================================
import argparse, csv, json, re, time, os, urllib.request, urllib.error

csv.field_size_limit(10**8)
ROOT = os.path.dirname(os.path.abspath(__file__))
def _find_data():
    for c in (os.path.join(ROOT,"data"), os.path.join(os.path.dirname(ROOT),"data")):
        if os.path.exists(os.path.join(c,"master_news_narrative_v2.csv")): return c
    return os.path.join(ROOT,"data")
DATA=_find_data(); OUT=os.path.join(ROOT,"sixw_out"); os.makedirs(OUT,exist_ok=True)

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-4-5-20251001"          # 원본과 동일
KEY_RE = re.compile(r"(sk-ant-[A-Za-z0-9\-_]+)")

SYSTEM_PROMPT = """You are a strict NLI-style factual consistency auditor for an academic benchmark.
Use only the source article as ground truth. Do not use outside knowledge.
Count atomic factual claims in the generated narrative.
Contradiction means a narrative claim directly conflicts with, reverses, or materially contradicts the source article.
Unsupported details that are not directly contradicted should be counted as neutral, not contradiction.
Return only JSON. Do not include markdown.
"""  # 원본 run_table2_cr_v2.py와 동일 (수정 금지)

USER_PROMPT_TEMPLATE = """Compute contradiction-rate components for the generated narrative against the source article.

Return JSON only:
{{
  "total_claims": integer,
  "contradicted_claims": integer,
  "contradiction_examples": ["short example if any"]
}}

Source title:
{title}

Source article:
{body}

Generated narrative:
{narrative}
"""  # 원본과 동일 (수정 금지)

def call(key, title, body, narrative, timeout=90, retries=5):
    payload = {"model": MODEL, "max_tokens": 1024, "system": SYSTEM_PROMPT,
               "messages": [{"role": "user", "content": USER_PROMPT_TEMPLATE.format(
                   title=title, body=body, narrative=narrative)}]}
    req = urllib.request.Request(API_URL, data=json.dumps(payload).encode(),
        headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                txt = json.loads(r.read())["content"][0]["text"]
            m = re.search(r"\{.*\}", txt, re.S)
            return json.loads(m.group(0))
        except Exception as e:
            if i == retries-1: raise
            time.sleep(2 * (i+1))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", default=os.path.join(os.path.dirname(ROOT), "keys.txt"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.2)
    a = ap.parse_args()
    key = KEY_RE.search(open(a.keys, encoding="utf-8", errors="ignore").read())
    if not key: raise SystemExit("keys.txt에서 claude 키(sk-ant-...)를 못 찾음")
    key = key.group(1)

    arts = {}
    with open(os.path.join(DATA, "master_articles_2000.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f): arts[r["url"]] = (r.get("title",""), r.get("body",""))
    outp = os.path.join(OUT, "cr_claims_neutral.csv")
    done = set()
    if os.path.exists(outp):
        done = {r["gen_id"] for r in csv.DictReader(open(outp, encoding="utf-8"))}
    hdr = ["gen_id","article_id","url","gen_model_family","perspective","stratum",
           "total_claims","contradicted_claims","cr_claim","contradiction_examples","cr_zero"]
    new = not os.path.exists(outp)
    fout = open(outp, "a", newline="", encoding="utf-8"); w = csv.writer(fout)
    if new: w.writerow(hdr)
    n=0; t0=time.time()
    with open(os.path.join(DATA, "master_news_narrative_v2.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("stratum") != "neutral_2026-07": continue
            if (r.get("is_possible") or "").upper() != "Y": continue
            gid = r.get("gen_id","")
            if gid in done: continue
            if a.limit and n >= a.limit: break
            title, body = arts.get(r["url"], ("",""))
            try:
                res = call(key, title, body, r["output_text"])
                tc = int(res.get("total_claims") or 0); cc = int(res.get("contradicted_claims") or 0)
                cr = (cc/tc) if tc else 0.0
                w.writerow([gid, r.get("article_id",""), r["url"], r.get("gen_model_family",""),
                            r.get("perspective",""), r["stratum"], tc, cc, f"{cr:.6f}",
                            json.dumps(res.get("contradiction_examples") or [], ensure_ascii=False)[:500],
                            1 if (tc and cc==0) else 0])
                fout.flush(); n+=1
                if n % 25 == 0: print(f"  {n}건 ({time.time()-t0:.0f}s)", flush=True)
                time.sleep(a.sleep)
            except Exception as e:
                print(f"[err] {gid}: {e}", flush=True)
    fout.close()
    print(f"완료: 신규 {n}건 → {outp}")
    print("다음: master_cr_claims.csv와 스키마 정합 확인 후 병합 (cr_zero 정의 동일: total>0 & contradicted=0).")

if __name__ == "__main__":
    main()
