# =============================================================
# run_sixw_extract.py — 3층위(원문·요약·관점 서술)에 동일 추출기 실행
# 2026-07-28. API 불필요. 재개형(progress 파일 기준 이어감).
#
# 실행:
#   !pip -q install spacy && python -m spacy download en_core_web_sm
#   python run_sixw_extract.py --layer all
#   (개별)  --layer source | summary | narrative
#   (표본)  --limit 200     ← 스모크 확인용
#
# 입력 (data/ 아래, 마스터 v2 기준):
#   master_articles_2000.csv        원문 1,999 (body)
#   master_summaries.csv            요약 17,991 (기본: 압축률 0.55만 → --cr all 로 전량)
#   master_news_narrative_v2.csv    관점 서술 1,999행 중 is_possible=Y 1,926
# 출력 (sixw_out/):
#   {layer}_{srl,attribution,causal,temporal,place}.csv   구분자 '|'
#   {layer}_progress.txt / errors.log
# =============================================================
import os, sys, csv, argparse, time

csv.field_size_limit(10**8)
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(ROOT, "sixw_out")

def _find_data():
    """data/ 를 자기 폴더 → 상위 폴더 순으로 찾는다.
    sixw/ 를 code/ 아래에 둔 경우 상위의 기존 data/ 를 그대로 쓸 수 있다."""
    need = "master_articles_2000.csv"
    for cand in (os.path.join(ROOT, "data"), os.path.join(os.path.dirname(ROOT), "data")):
        if os.path.exists(os.path.join(cand, need)):
            return cand
    return os.path.join(ROOT, "data")

DATA = _find_data()
os.makedirs(OUT, exist_ok=True)
SEP = "|"

sys.path.insert(0, ROOT)
import spacy
from sixw_extractors import set_nlp, EXTRACTORS

def log(*a): print(*a, flush=True)

def ensure_header(path, header):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f, delimiter=SEP).writerow(header)

def append(path, rows):
    if not rows: return
    with open(path, "a", newline="", encoding="utf-8") as f:
        csv.writer(f, delimiter=SEP).writerows(rows)

def load_done(p):
    if not os.path.exists(p): return set()
    return set(l.strip() for l in open(p, encoding="utf-8") if l.strip())

def mark(p, k):
    with open(p, "a", encoding="utf-8") as f: f.write(k + "\n")

# ---------- 입력 이터레이터: (key, text, meta) ----------
def iter_source(limit=None, **kw):
    p = os.path.join(DATA, "master_articles_2000.csv")
    with open(p, encoding="utf-8") as f:
        for i, r in enumerate(csv.DictReader(f)):
            if limit and i >= limit: break
            t = (r.get("body") or "").strip()
            if t: yield r["url"], t, {"url": r["url"], "gen_model": "", "cr": "", "perspective": ""}

def iter_summary(limit=None, cr="0.55", **kw):
    p = os.path.join(DATA, "master_summaries.csv")
    with open(p, encoding="utf-8") as f:
        n = 0
        for r in csv.DictReader(f):
            if cr != "all" and str(r.get("compression_ratio")) != cr: continue
            t = (r.get("summary_text") or r.get("output_text") or "").strip()
            if not t: continue
            if limit and n >= limit: break
            n += 1
            key = f"{r['url']}::{r.get('gen_model_family','')}::{r.get('compression_ratio','')}"
            yield key, t, {"url": r["url"], "gen_model": r.get("gen_model_family",""),
                           "cr": r.get("compression_ratio",""), "perspective": ""}

def iter_narrative(limit=None, **kw):
    p = os.path.join(DATA, "master_news_narrative_v2.csv")
    if not os.path.exists(p):
        p = os.path.join(DATA, "master_news_narrative.csv")
        log("[warn] v2 없음 → v1 사용 (중립층 481 누락)")
    with open(p, encoding="utf-8") as f:
        n = 0
        for r in csv.DictReader(f):
            if (r.get("is_possible") or "Y").strip().upper() != "Y": continue
            t = (r.get("output_text") or "").strip()
            if not t: continue
            if limit and n >= limit: break
            n += 1
            key = r.get("gen_id") or f"{r['url']}::{r.get('perspective','')}"
            yield key, t, {"url": r["url"], "gen_model": r.get("gen_model_family",""),
                           "cr": "", "perspective": r.get("perspective","")}

LAYERS = {"source": iter_source, "summary": iter_summary, "narrative": iter_narrative}
META_COLS = ["key", "url", "gen_model", "cr", "perspective"]

def run_layer(layer, limit=None, cr="0.55", batch_size=32, procs=1):
    it = LAYERS[layer]
    prog = os.path.join(OUT, f"{layer}_progress.txt")
    errp = os.path.join(OUT, f"{layer}_errors.log")
    done = load_done(prog)
    paths = {}
    for name, (_fn, hdr) in EXTRACTORS.items():
        p = os.path.join(OUT, f"{layer}_{name}.csv")
        ensure_header(p, META_COLS + hdr)
        paths[name] = p
    t0 = time.time(); n = 0; skipped = 0

    def flush(batch):
        """배치 단위: pipe로 한 번에 파싱(prime) → 추출기는 전부 캐시 적중"""
        nonlocal n
        if not batch: return
        from sixw_extractors import _NLP
        try:
            _NLP.prime([b[1] for b in batch], batch_size=batch_size, n_process=procs)
        except Exception as e:
            with open(errp, "a", encoding="utf-8") as f: f.write(f"[prime]\t{e}\n")
        for key, text, meta in batch:
            mrow = [key, meta["url"], meta["gen_model"], meta["cr"], meta["perspective"]]
            for name, (fn, _hdr) in EXTRACTORS.items():
                try:
                    rows = fn(text)
                except Exception as e:
                    rows = []
                    with open(errp, "a", encoding="utf-8") as f: f.write(f"{key}\t{name}\t{e}\n")
                append(paths[name], [mrow + list(r) for r in rows])
            mark(prog, key); n += 1

    batch = []
    for key, text, meta in it(limit=limit, cr=cr):
        if key in done:
            skipped += 1; continue
        batch.append((key, text, meta))
        if len(batch) >= batch_size:
            flush(batch); batch = []
            try:
                from sixw_extractors import nlp_stats
                pa, hi = nlp_stats()
                log(f"  {layer}: {n}건 ({time.time()-t0:.0f}s, 파싱 {pa} / 캐시적중 {hi})")
            except Exception:
                log(f"  {layer}: {n}건 ({time.time()-t0:.0f}s)")
    flush(batch)
    log(f"[{layer}] 신규 {n}건 / 스킵 {skipped}건 / {time.time()-t0:.0f}s")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", default="all", choices=["all", "source", "summary", "narrative"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--cr", default="0.55", help="요약 압축률 필터 ('all' 가능)")
    ap.add_argument("--batch", type=int, default=32, help="spaCy pipe 배치 크기 (원문은 길어서 16~32 권장)")
    ap.add_argument("--procs", type=int, default=1, help="spaCy pipe 프로세스 수 (코랩 2코어면 2)")
    a = ap.parse_args()
    log(f"DATA = {DATA}")
    log("spaCy 로딩...")
    nlp = spacy.load("en_core_web_sm")
    nlp.max_length = 3_000_000
    set_nlp(nlp)   # 문서당 1회 파싱 캐시로 감싸서 주입
    todo = ["source", "summary", "narrative"] if a.layer == "all" else [a.layer]
    for L in todo:
        log(f"=== {L} ===")
        run_layer(L, limit=a.limit, cr=a.cr, batch_size=a.batch, procs=a.procs)
    log("완료. 다음: python run_sixw_aggregate.py")
