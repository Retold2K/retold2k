# =============================================================
# phase0a_extractors.py — 규칙 기반 구조 추출 함수 (Phase 0a, Phase 2 공유)
# Phase 0a와 Phase 2가 반드시 동일한 추출을 쓰도록 분리.
# spaCy 필요: nlp = spacy.load("en_core_web_sm") 가 전역에 있어야 함.
#   사용 전: import spacy; nlp = spacy.load("en_core_web_sm")
#            그 다음 from phase0a_extractors import set_nlp, extract_srl, ...
#            set_nlp(nlp) 로 주입
# =============================================================
import re

_NLP = None
def set_nlp(nlp):
    global _NLP
    _NLP = nlp

def _np(token, sent):
    """토큰이 속한 명사구 전체 텍스트 (없으면 토큰 자체). B2: 'Province'→'The ANC Gauteng Province'"""
    try:
        for chunk in sent.noun_chunks:
            if token.i >= chunk.start and token.i < chunk.end:
                return chunk.text
    except Exception:
        pass
    return token.text

def _clean(s):
    if s is None:
        return ""
    return re.sub(r"\s+", " ", str(s).replace("|", "/").replace("\n", " ")).strip()

# ---------- 술어-논항 (AR용) ----------
# 반환: [predicate, agent, patient, voice, agent_present, sent_id, position, sentence]
def extract_srl(text):
    rows = []
    doc = _NLP(text)
    sents = list(doc.sents)
    for sent_id, sent in enumerate(sents):
        position = "lead" if sent_id < 2 else "body"
        stext = _clean(sent.text)
        for tok in sent:
            if tok.pos_ != "VERB":
                continue
            predicate = tok.lemma_.lower()
            subj     = [c for c in tok.children if c.dep_ == "nsubj"]
            subjpass = [c for c in tok.children if c.dep_ == "nsubjpass"]
            dobj     = [c for c in tok.children if c.dep_ in ("dobj", "obj")]
            by_agent = [c for c in tok.children if c.dep_ == "agent"]
            if subjpass:
                agent_txt = ""
                if by_agent:
                    pobj = [g for c in by_agent for g in c.children if g.dep_ == "pobj"]
                    agent_txt = _np(pobj[0], sent) if pobj else ""
                rows.append([predicate, _clean(agent_txt), _clean(_np(subjpass[0], sent)),
                             "passive", 1 if agent_txt else 0, sent_id, position, stext])
            elif subj:
                patient = _np(dobj[0], sent) if dobj else ""
                rows.append([predicate, _clean(_np(subj[0], sent)), _clean(patient),
                             "active", 1, sent_id, position, stext])
    return rows

# ---------- 출처 표지 (AS용) ----------
# 반환: [cue, source, sentence, sent_id, position]
ATTR_CUES = {"say","tell","report","claim","allege","state","announce","accuse"}
def extract_attribution(text):
    rows = []
    doc = _NLP(text)
    for sent_id, sent in enumerate(doc.sents):
        position = "lead" if sent_id < 2 else "body"
        stext = _clean(sent.text)
        for tok in sent:
            lemma = tok.lemma_.lower()
            if tok.text.lower() == "according":
                src = ""
                for c in tok.children:
                    if c.dep_ == "prep" and c.text.lower() == "to":
                        pobj = [g for g in c.children if g.dep_ == "pobj"]
                        if pobj:
                            src = _np(pobj[0], sent)
                rows.append(["according to", _clean(src), stext, sent_id, position])
            elif lemma in ATTR_CUES and tok.pos_ == "VERB":
                subj = [c for c in tok.children if c.dep_ in ("nsubj", "nsubjpass")]
                rows.append([_clean(lemma), _clean(_np(subj[0], sent) if subj else ""),
                             stext, sent_id, position])
    return rows

# ---------- 인과 표지 (CD용) ----------
# 반환: [cue, cause, effect, sent_id, position, is_quoted, sentence]
CAUSAL = ["because of","because","due to","as a result of","caused by",
          "led to","owing to","prompted by","resulted in","thanks to"]
def extract_causal(text):
    rows = []
    doc = _NLP(text)
    for sent_id, sent in enumerate(doc.sents):
        position = "lead" if sent_id < 2 else "body"
        stext = sent.text
        low = stext.lower()
        for cue in CAUSAL:
            # B1: 단어 경계 매칭 ("appealed to"의 'led to' 오탐 방지)
            m = re.search(r"\b" + re.escape(cue) + r"\b", low)
            if not m:
                continue
            idx = m.start()
            before, after = stext[:idx].strip(), stext[m.end():].strip()
            if cue in ("led to", "resulted in"):
                cause, effect = before, after
            else:
                cause, effect = after, before
            # B3: 인용문 내 인과 플래그 (화자의 인과 vs 기자의 인과 구분용)
            is_quoted = 1 if ('"' in stext or chr(0x201C) in stext) else 0
            rows.append([_clean(cue), _clean(cause), _clean(effect),
                         sent_id, position, is_quoted, _clean(stext)])
            break
    return rows
