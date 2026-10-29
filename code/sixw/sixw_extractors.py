# =============================================================
# sixw_extractors.py — 육하원칙 구조 추출 (원문·요약·관점 서술 공용)
# 2026-07-28. 레거시 phase0a_extractors.py의 SRL/출처/인과를 그대로 재사용하고,
# 시간(when)·장소(where) 추출을 추가한다. 세 층위에 반드시 같은 함수를 쓴다 — 비교 가능성의 전제.
#
# 사용:
#   import spacy; nlp = spacy.load("en_core_web_sm")
#   from sixw_extractors import set_nlp, extract_all
#   set_nlp(nlp)
#   rows = extract_all(text)
#
# 설계 원칙
#  1) 규칙 기반 = API 불필요, 심판 순환성 없음
#  2) 레거시 3함수는 코드를 바꾸지 않는다 (원문·요약 기존 산출물과 동일성 보장)
#  3) 신규 2함수(시간·장소)는 spaCy NER + 정규식 병용, 둘 중 하나만 잡혀도 앵커로 인정
# =============================================================
import re

_NLP = None

class _CachingNLP:
    """추출기 6종이 각자 nlp(text)를 부르므로 같은 문서를 6번 파싱하게 된다.
    (1) 한 칸 캐시로 문서당 1회만 파싱한다.
    (2) prime()으로 nlp.pipe() 배치 결과를 미리 채워 두면, 추출기 호출은 전부 캐시 적중이 되고
        실제 파싱은 배치 단위로만 일어난다 — spaCy는 pipe가 개별 호출보다 빠르다.
    추출기 본문은 손대지 않는다 (레거시 무수정 원칙)."""
    def __init__(self, nlp):
        self._nlp = nlp
        self._key = None
        self._doc = None
        self._batch = {}     # prime()으로 채운 text -> doc
        self.parses = 0      # 실제 파싱 문서 수 (검증용)
        self.hits = 0        # 캐시 적중 횟수
    def prime(self, texts, batch_size=64, n_process=1):
        """텍스트 목록을 배치로 파싱해 캐시에 적재. pipe 미지원 객체면 개별 호출로 폴백."""
        self._batch = {}
        pipe = getattr(self._nlp, "pipe", None)
        if callable(pipe):
            try:
                kw = {"batch_size": batch_size}
                if n_process and n_process > 1:
                    kw["n_process"] = n_process
                for tx, doc in zip(texts, pipe(texts, **kw)):
                    self._batch[tx] = doc
                    self.parses += 1
                return len(self._batch)
            except Exception:
                self._batch = {}
        for tx in texts:
            self._batch[tx] = self._nlp(tx); self.parses += 1
        return len(self._batch)
    def __call__(self, text):
        d = self._batch.get(text)
        if d is not None:
            self.hits += 1
            return d
        if text is self._key or text == self._key:
            self.hits += 1
            return self._doc
        self._doc = self._nlp(text)
        self._key = text
        self.parses += 1
        return self._doc
    def __getattr__(self, name):
        return getattr(self._nlp, name)

def set_nlp(nlp):
    """실제 spaCy 객체를 받아 캐싱 래퍼로 감싼 뒤 이 모듈과 레거시 모듈에 함께 주입."""
    global _NLP
    _NLP = nlp if isinstance(nlp, _CachingNLP) else _CachingNLP(nlp)
    try:
        import phase0a_extractors_legacy as L
        L.set_nlp(_NLP)
    except Exception:
        pass
    return _NLP

def nlp_stats():
    return (getattr(_NLP, "parses", None), getattr(_NLP, "hits", None))

def _clean(s):
    if s is None: return ""
    return re.sub(r"\s+", " ", str(s).replace("|", "/").replace("\n", " ")).strip()

# ---------- 레거시 3종 (원문·요약과 완전 동일) ----------
def extract_srl(text):
    import phase0a_extractors_legacy as L
    return L.extract_srl(text)

def extract_attribution(text):
    import phase0a_extractors_legacy as L
    return L.extract_attribution(text)

def extract_causal(text):
    import phase0a_extractors_legacy as L
    return L.extract_causal(text)

# ---------- 신규: 시간 (when) ----------
_MONTH = (r"(?:January|February|March|April|May|June|July|August|September|October|November|December"
          r"|Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|Aug\.?|Sept?\.?|Oct\.?|Nov\.?|Dec\.?)")
_DAY   = r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
_NUMW  = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
_REL   = (r"(?:yesterday|today|tomorrow|tonight"
          r"|last (?:week|month|year|night|summer|winter|spring|autumn|fall)"
          r"|this (?:week|month|year|morning|afternoon|evening)"
          r"|next (?:week|month|year)"
          r"|earlier (?:this|that) \w+|that (?:morning|afternoon|evening|night|day)"
          rf"|{_NUMW} (?:seconds?|minutes?|hours?|days?|weeks?|months?|years?|decades?) (?:ago|earlier|later|before|after)"
          r"|moments? (?:later|earlier|before|after)|soon after|shortly (?:after|before)"
          r"|by (?:dawn|dusk|nightfall|morning|noon|midnight))")
_ABS   = rf"(?:{_MONTH}\s+\d{{1,2}}(?:,\s*\d{{4}})?|\d{{1,2}}\s+{_MONTH}(?:\s+\d{{4}})?|\b(?:1[0-9]|20)\d{{2}}\b|\d{{1,2}}:\d{{2}}\s*(?:a\.?m\.?|p\.?m\.?)?)"
_TIME_RE = re.compile(rf"({_ABS}|{_DAY}|{_REL})", re.I)

# 절대/상대 구분: 원문 대조가 가능한 것(절대)과 서사가 만들어내는 것(상대)을 분리해야
# "앵커 손실"과 "시간선 창작"을 구별할 수 있다.
_ABS_ONLY = re.compile(rf"^(?:{_ABS}|{_DAY})$", re.I)

def extract_temporal(text):
    """반환: [surface, kind(absolute|relative), source(ner|regex|both), sent_id, position, sentence]"""
    rows = []
    doc = _NLP(text)
    ner_spans = {}
    for ent in doc.ents:
        if ent.label_ in ("DATE", "TIME"):
            ner_spans[(ent.start_char, ent.end_char)] = ent.text
    ner_texts = {v.lower().strip() for v in ner_spans.values()}
    for sent_id, sent in enumerate(doc.sents):
        position = "lead" if sent_id < 2 else "body"
        stext = _clean(sent.text)
        found = {}
        for m in _TIME_RE.finditer(sent.text):
            s = m.group(0).strip()
            found[s.lower()] = ("regex", s)
        for ent in sent.ents:
            if ent.label_ in ("DATE", "TIME"):
                k = ent.text.lower().strip()
                found[k] = ("both", ent.text) if k in found else ("ner", ent.text)
        for k, (src, surface) in found.items():
            kind = "absolute" if _ABS_ONLY.match(surface.strip()) else "relative"
            rows.append([_clean(surface), kind, src, sent_id, position, stext])
    return rows

# ---------- 신규: 장소 (where) ----------
_PLACE_LABELS = ("GPE", "LOC", "FAC")

def extract_place(text):
    """반환: [surface, label(GPE|LOC|FAC), sent_id, position, sentence]"""
    rows = []
    doc = _NLP(text)
    for sent_id, sent in enumerate(doc.sents):
        position = "lead" if sent_id < 2 else "body"
        stext = _clean(sent.text)
        seen = set()
        for ent in sent.ents:
            if ent.label_ in _PLACE_LABELS:
                k = (ent.text.lower().strip(), ent.label_)
                if k in seen: continue
                seen.add(k)
                rows.append([_clean(ent.text), ent.label_, sent_id, position, stext])
    return rows

# ---------- 신규: 방식·수단 (how) ----------
# 책임 판단에서 수단은 핵심이다 ("칼로 살해했다" vs "사망했다"에서 사라지는 것이 how).
# 세 하위로 나눈다: instrument(도구·수단 명사) / means(by -ing) / manner(방식 부사).
# spaCy 의존구조로 전치사구를 잡고, 부사는 advmod에서 가져온다. 정규식 폴백 병용.
_INSTR_PREP = {"with", "using", "via", "through"}
_MANNER_STOP = {"only","likely","early","family","reportedly","allegedly","apparently","recently",
                "currently","previously","finally","initially","simply","usually","probably",
                "possibly","nearly","really","actually","especially","particularly","generally",
                "immediately","shortly","briefly","respectively","approximately","subsequently"}
_INSTR_RE = re.compile(r"\b(?:with|using|by means of|via)\s+(?:a |an |the |his |her |their |its )?([a-z][\w-]*)", re.I)
_BYING_RE = re.compile(r"\bby\s+(\w+ing)\b", re.I)
_MANNER_RE = re.compile(r"\b(\w{5,}ly)\b")

def extract_manner(text):
    """반환: [surface, subtype(instrument|means|manner), detector, sent_id, position, sentence]"""
    rows = []
    doc = _NLP(text)
    for sent_id, sent in enumerate(doc.sents):
        position = "lead" if sent_id < 2 else "body"
        stext = _clean(sent.text)
        found = {}
        # 의존구조: 전치사구 도구 / by -ing / 방식 부사
        for tok in sent:
            try:
                if tok.dep_ == "prep" and tok.text.lower() in _INSTR_PREP:
                    for g in tok.children:
                        if g.dep_ == "pobj":
                            found[("instrument", _np(g, sent).lower())] = "dep"
                elif tok.dep_ == "prep" and tok.text.lower() == "by":
                    for g in tok.children:
                        if g.dep_ == "pcomp" or (g.dep_ == "pobj" and g.text.lower().endswith("ing")):
                            found[("means", g.text.lower())] = "dep"
                elif tok.dep_ == "advmod" and tok.text.lower().endswith("ly")                         and tok.text.lower() not in _MANNER_STOP and len(tok.text) > 4:
                    found[("manner", tok.text.lower())] = "dep"
            except Exception:
                pass
        # 정규식 폴백
        for m in _INSTR_RE.finditer(sent.text):
            w = m.group(1).lower()
            if len(w) > 2: found.setdefault(("instrument", w), "regex")
        for m in _BYING_RE.finditer(sent.text):
            found.setdefault(("means", m.group(1).lower()), "regex")
        for m in _MANNER_RE.finditer(sent.text):
            w = m.group(1).lower()
            if w not in _MANNER_STOP: found.setdefault(("manner", w), "regex")
        for (sub, surface), det in found.items():
            rows.append([_clean(surface), sub, det, sent_id, position, stext])
    return rows

def _np(token, sent):
    try:
        for chunk in sent.noun_chunks:
            if token.i >= chunk.start and token.i < chunk.end:
                return chunk.text
    except Exception:
        pass
    return token.text

# ---------- 통합 ----------
EXTRACTORS = {
    "srl":         (extract_srl,        ["predicate","agent","patient","voice","agent_present","sent_id","position","sentence"]),
    "attribution": (extract_attribution,["cue","source","sentence","sent_id","position"]),
    "causal":      (extract_causal,     ["cue","cause","effect","sent_id","position","is_quoted","sentence"]),
    "temporal":    (extract_temporal,   ["surface","kind","detector","sent_id","position","sentence"]),
    "place":       (extract_place,      ["surface","label","sent_id","position","sentence"]),
    "manner":      (extract_manner,     ["surface","subtype","detector","sent_id","position","sentence"]),
}

def extract_all(text):
    out = {}
    for name, (fn, _hdr) in EXTRACTORS.items():
        try:
            out[name] = fn(text)
        except Exception as e:
            out[name] = []
            out.setdefault("_errors", []).append(f"{name}: {e}")
    return out
