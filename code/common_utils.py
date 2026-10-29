# =============================================================
# common_utils.py — 모든 Phase 공통 유틸
#   from common_utils import *
# =============================================================
import os, re, csv, time, itertools
import pandas as pd

# ---------- 경로 ----------
ROOT = os.path.dirname(os.path.abspath(__file__))  # 번들 폴더 기준
DATA_CSV = os.path.join(ROOT, "data", "experiment_data_refilled_update.csv")
KEYS_TXT = os.path.join(ROOT, "keys.txt")
DELIM = "|"

def phase_dir(name):
    """phase 폴더 생성 후 경로 반환. 예: phase_dir('phase0')"""
    d = os.path.join(ROOT, name)
    os.makedirs(d, exist_ok=True)
    return d

# ---------- 텍스트 정리 ----------
def clean(s):
    """구분자(|)·개행 충돌 방지."""
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s).replace("|", "/").replace("\n", " ")).strip()

# ---------- CSV 헬퍼 ----------
def ensure_header(path, header):
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f, delimiter=DELIM).writerow(header)

def append_rows(path, rows):
    """매 호출마다 열고 flush 후 닫음 → 런타임 끊겨도 디스크 반영 보장(R5)."""
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=DELIM)
        for r in rows:
            w.writerow(r)
        f.flush()
        os.fsync(f.fileno())

def read_csv(path):
    return pd.read_csv(path, sep=DELIM)

# ---------- 진행상태 (재실행 안전) ----------
def load_done(prog_path, key_col="key"):
    if os.path.exists(prog_path):
        return set(pd.read_csv(prog_path, sep=DELIM)[key_col].astype(str))
    ensure_header(prog_path, [key_col, "done"])
    return set()

def mark_done(prog_path, key):
    with open(prog_path, "a", newline="", encoding="utf-8") as f:
        csv.writer(f, delimiter=DELIM).writerow([key, 1])
        f.flush(); os.fsync(f.fileno())

def log_err(err_path, msg):
    with open(err_path, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

# ---------- 키 로딩 ----------
def load_keys():
    """keys.txt('name : value') → dict. gpt/claude/gemini_1.. 모두."""
    keys = {}
    with open(KEYS_TXT, encoding="utf-8") as f:
        for line in f:
            if ":" in line:
                k, v = line.split(":", 1)
                keys[k.strip()] = v.strip()
    return keys

def gemini_keys():
    keys = load_keys()
    gem = [v for k, v in sorted(keys.items()) if k.startswith("gemini")]
    if not gem:
        raise RuntimeError("keys.txt에 gemini_* 키가 없습니다.")
    return gem

# ---------- Gemini 키 로테이터 ----------
class GeminiRotator:
    """여러 gemini 키를 순환하며 rate limit 회피."""
    def __init__(self, model_name="gemini-3.1-flash-lite", temperature=0.0):
        import google.generativeai as genai
        self.genai = genai
        self.keys = gemini_keys()
        self.model_name = model_name
        self.temperature = temperature
        self._cycle = itertools.cycle(range(len(self.keys)))
        self.cur = 0
        self._set_next()
        print(f"GeminiRotator: {len(self.keys)} keys, model={model_name}")

    def _set_next(self):
        self.cur = next(self._cycle)
        self.genai.configure(api_key=self.keys[self.cur])

    @staticmethod
    def _is_quota(msg):
        # 주의: 맨몸 "rate"는 금지 — 차단 메시지의 'generate-content' URL에 부분 매칭됨
        return ("429" in msg or "quota" in msg
                or "resource has been exhausted" in msg
                or "rate limit" in msg)

    def generate(self, prompt, max_retry=None, sleep=1.2, cycle_wait=45):
        """Phase 0 운영 교훈 반영판:
        - 콘텐츠 차단(BLOCKED)은 즉시 실패 (키 회전 무의미 — 차단은 기사를 따라감)
        - quota 판별에 맨몸 "rate" 금지 (차단 메시지의 'generate'에 오매칭)
        - 한 바퀴 전멸 시 cycle_wait초 대기 (분당 윈도 리셋이 회전보다 느림)
        - self.stats로 운영 현황 집계
        """
        n = len(self.keys)
        if max_retry is None:
            max_retry = n * 3            # 최대 3바퀴
        if not hasattr(self, "stats"):
            self.stats = {"ok": 0, "blocked": 0, "quota_retries": 0, "cycle_waits": 0}
        last = None
        tried = []
        for i in range(max_retry):
            tried.append(self.cur)
            try:
                model = self.genai.GenerativeModel(
                    self.model_name,
                    generation_config={"temperature": self.temperature})
                # 기본 600초 타임아웃 과도(멈춘 요청 1건=10분). 60초: 정상 장문응답은 살리고 행만 컷
                resp = model.generate_content(
                    prompt, request_options={"timeout": 60})
                # 응답에 Part가 없으면 콘텐츠 차단 → 재시도/회전 무의미, 즉시 실패
                if not resp.candidates or not resp.candidates[0].content.parts:
                    fr = (resp.candidates[0].finish_reason
                          if resp.candidates else "PROMPT_BLOCKED")
                    self.stats["blocked"] += 1
                    raise RuntimeError(f"BLOCKED finish_reason={fr}")
                self.stats["ok"] += 1
                return resp.text or ""
            except Exception as e:
                if "BLOCKED" in str(e):
                    raise                 # 차단은 그대로 위로 (로그에 BLOCKED로 남음)
                last = e
                msg = str(e).lower()
                quota = self._is_quota(msg)
                hung = ("timed out" in msg or "timeout" in msg or "deadline" in msg)
                if not (quota or hung):
                    raise                 # quota/타임아웃 외 오류는 회전 무의미
                self.stats["quota_retries"] += 1
                self._set_next()
                time.sleep(sleep)
                if quota and (i + 1) % n == 0:  # 한 바퀴 전부 quota면 분당 윈도 리셋 대기
                    self.stats["cycle_waits"] += 1
                    print(f"  (전 키 한바퀴 quota — 시도한 키 {tried[-n:]} — {cycle_wait}초 대기)")
                    time.sleep(cycle_wait)
        raise RuntimeError(f"ALL_KEYS_EXHAUSTED after {max_retry} tries: {last}")

# ---------- 데이터 로딩 ----------
def load_dataset(pilot=False, pilot_per_group=5, seed=42):
    df = pd.read_csv(DATA_CSV).dropna(subset=["body"]).copy()
    if pilot:
        # 무작위 표본 (head()는 수집 순서 편향 — Phase0에서 Causal 3배 오차 유발)
        df = (df.groupby("safety_pressure", group_keys=False)
                .apply(lambda g: g.sample(min(pilot_per_group, len(g)), random_state=seed)))
    return df


# =============================================================
# 확장: 멀티 프로바이더 LLM 어댑터 (Phase 1, 3에서 사용)
# =============================================================

# ---------- OpenAI (GPT) ----------
class OpenAIClient:
    def __init__(self, model_name="gpt-5.4-mini", temperature=0.0):
        from openai import OpenAI
        keys = load_keys()
        if "gpt" not in keys:
            raise RuntimeError("keys.txt에 gpt 키가 없습니다.")
        self.client = OpenAI(api_key=keys["gpt"], timeout=120, max_retries=2)
        self.model_name = model_name
        self.temperature = temperature

    def generate(self, prompt, system=None, max_retry=4, sleep=2.0):
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        last = None
        for _ in range(max_retry):
            try:
                r = self.client.chat.completions.create(
                    model=self.model_name, messages=msgs,
                    temperature=self.temperature)
                finish = r.choices[0].finish_reason
                return (r.choices[0].message.content or ""), finish
            except Exception as e:
                last = e; time.sleep(sleep)
        raise RuntimeError(f"OpenAI failed: {last}")

# ---------- Anthropic (Claude) ----------
class ClaudeClient:
    def __init__(self, model_name="claude-haiku-4-5", temperature=0.0):
        import anthropic
        keys = load_keys()
        if "claude" not in keys:
            raise RuntimeError("keys.txt에 claude 키가 없습니다.")
        self.client = anthropic.Anthropic(api_key=keys["claude"], timeout=120, max_retries=2)
        self.model_name = model_name
        self.temperature = temperature

    def generate(self, prompt, system=None, max_retry=4, sleep=2.0, max_tokens=1024):
        last = None
        for _ in range(max_retry):
            try:
                kw = dict(model=self.model_name, max_tokens=max_tokens,
                          temperature=self.temperature,
                          messages=[{"role": "user", "content": prompt}])
                if system:
                    kw["system"] = system
                r = self.client.messages.create(**kw)
                txt = "".join(b.text for b in r.content if hasattr(b, "text"))
                return txt, r.stop_reason
            except Exception as e:
                last = e; time.sleep(sleep)
        raise RuntimeError(f"Claude failed: {last}")

# ---------- Gemini (generate에 system 인자 추가 래퍼) ----------
class GeminiClient:
    """GeminiRotator를 OpenAI/Claude와 같은 인터페이스(generate->(text,finish))로 감쌈."""
    def __init__(self, model_name="gemini-3.1-flash-lite", temperature=0.0):
        self.rot = GeminiRotator(model_name=model_name, temperature=temperature)

    def generate(self, prompt, system=None, **kw):
        full = (system + "\n\n" + prompt) if system else prompt
        txt = self.rot.generate(full)
        return txt, "stop"

# ---------- 통합 팩토리 ----------
# 모델 식별자(짧은 별칭) -> (provider, api_string)
MODEL_REGISTRY = {
    "gpt":    ("openai", "gpt-5.4-mini"),
    "claude": ("claude", "claude-haiku-4-5"),
    "gemini": ("gemini", "gemini-3.1-flash-lite"),
}

def make_client(alias, temperature=0.0):
    provider, api_str = MODEL_REGISTRY[alias]
    if provider == "openai":
        return OpenAIClient(api_str, temperature)
    if provider == "claude":
        return ClaudeClient(api_str, temperature)
    if provider == "gemini":
        return GeminiClient(api_str, temperature)
    raise ValueError(alias)

# leave-one-family-out: 생성 모델 별칭 -> 판정 모델 별칭 2개
JUDGE_MAP = {
    "gpt":    ["claude", "gemini"],
    "claude": ["gpt", "gemini"],
    "gemini": ["gpt", "claude"],
}

# ---------- 조인 헬퍼 ----------
def join_key(row, cols=("url", "gen_model", "compression_ratio")):
    return "||".join(str(row[c]) for c in cols)

def refusal_detect(text, finish_reason=""):
    """거부 판정(공통 규칙)."""
    if finish_reason and ("content_filter" in str(finish_reason).lower()):
        return True
    if not text or len(text.strip()) < 20:
        return True
    patterns = ["i can't", "i cannot", "i'm unable", "i am unable",
                "i won't", "as an ai", "i'm sorry, but", "cannot assist",
                "can't help with", "unable to provide"]
    low = text.lower()
    return any(p in low for p in patterns)


# =============================================================
# 운영 헬퍼 (Phase 0 운영 경험 반영)
# =============================================================
def quiet_logs():
    """429 재시도 시 tornado가 찍는 WARNING 폭주 무음화 (동작 무관, 표시만)."""
    import logging
    logging.getLogger("tornado.access").setLevel(logging.ERROR)

quiet_logs()  # import 시 자동 적용

def run_status(prog_path, total):
    """진행 현황 한 줄."""
    done = (sum(1 for _ in open(prog_path)) - 1) if os.path.exists(prog_path) else 0
    print(f"완료 {done} / {total} (남은 {total - done})")
    return done

def eta(prog_path, total, wait=60):
    """wait초 간격 처리율로 남은 시간 추정."""
    n1 = run_status(prog_path, total)
    time.sleep(wait)
    n2 = (sum(1 for _ in open(prog_path)) - 1) if os.path.exists(prog_path) else 0
    rate = (n2 - n1) * (60 / wait)
    remain = total - n2
    print(f"분당 {rate:.0f}건 → 남은 시간 ≈ {remain / max(rate, 0.1):.0f}분")

def dedup_csv(path, subset=None):
    """중단-재시작으로 생긴 완전 중복 행 정리 (백업 후 재작성)."""
    import shutil
    shutil.copy(path, path + ".bak")
    df = pd.read_csv(path, sep=DELIM)
    before = len(df)
    df = df.drop_duplicates(subset=subset)
    df.to_csv(path, sep=DELIM, index=False)
    print(f"중복 {before - len(df)}행 제거 ({before} → {len(df)}), 백업: {path}.bak")
    return before - len(df)


def strip_markdown(text):
    """요약 텍스트의 마크다운 표면 형식 제거 (Phase 1 관찰: Claude 98%가 헤더 부착).
    마커만 벗기고 텍스트 내용은 보존 — 결정적·문서화 가능 (Appendix B.2)."""
    import re
    t = str(text)
    t = re.sub(r"^\s{0,3}#{1,6}\s+", "", t, flags=re.M)        # 헤더 마커
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t, flags=re.S)      # bold
    t = re.sub(r"__(.+?)__", r"\1", t, flags=re.S)
    t = re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"\1", t)    # italic (보수적)
    t = re.sub(r"^\s*[-*•]\s+", "", t, flags=re.M)             # 불릿 마커
    t = re.sub(r"^\s*\d+\.\s+", "", t, flags=re.M)           # 번호 목록
    t = re.sub(r"`([^`]*)`", r"\1", t)                          # 인라인 코드
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()
