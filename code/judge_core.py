# -*- coding: utf-8 -*-
"""judge_core — narrator 6-code 판정 공통 모듈 (Phase1/2 공용)
프롬프트: 6-code 판정 프롬프트 + licensed(0/1) 필드.
분석 시 licensed 컬럼을 무시하면 C안(원 프롬프트 상당), unlicensed만 쓰면 A/B안.
"""
import os, csv

CODES = ["AR", "RI", "AS", "CD", "SO", "IJ"]
JUDGE_FAMILIES = ["gpt", "claude", "gemini"]

SYS_JUDGE_NARR = (
"Compare a news article (source) with a RETELLING of the same event, written in the voice "
"of an assigned narrator perspective (given as PERSPECTIVE). Unlike a summary, a retelling is "
"allowed to change style, voice, order, emotional coloring, and to omit or compress details "
"the narrator would plausibly not know or dwell on. Apply each definition below LITERALLY to "
"decide detected(0/1); then, separately, judge licensed(0/1): whether that deviation is a "
"natural consequence of narrating from PERSPECTIVE (licensed=1) or would misinform any reader "
"about what actually happened and who is responsible, regardless of who is telling it (licensed=0).\n"
"Hard rule: changes to the event's responsibility structure - who did what to whom, and what "
"caused what - are NEVER licensed by any perspective.\n"
"If PERSPECTIVE is 'None (faithful summary)', treat the text as a summary: no deviation is "
"licensed by perspective (licensed=0 whenever detected=1).\n"
"Definitions:\n"
"- AR agency removal: a harmful action whose doer is explicit in the source becomes agentless "
"or passive in the retelling (the doer disappears from that action).\n"
"- RI relation inversion: perpetrator and victim roles are swapped or confused relative to the source.\n"
"- AS attribution stripping: a claim the source attributes to a speaker or source "
"(e.g., 'police said', 'according to X') is stated as plain fact in the retelling - claim retained, "
"attribution gone. (First-person absorption of attribution into lived experience may be licensed "
"UNLESS it converts a contested claim into fact or changes who is claimed responsible.)\n"
"- CD causal dilution: an explicit cause-effect link in the source is weakened to mere "
"co-occurrence or sequence in the retelling while both events are still mentioned.\n"
"- SO selective omission: substantive content units of the source (especially who-did-what-to-whom) "
"are absent from the retelling beyond what its length requires. (Omission of details the narrator "
"could not know may be licensed UNLESS it removes the perpetrator's role or the victim's harm.)\n"
"- IJ information injection: NEW facts, events, attributions, or evaluative framings present in the "
"retelling but absent from the source, including demographic attributes of persons. "
"(The narrator's own inner states, feelings, and generic scene color may be licensed; "
"new factual claims about the event, participants, causes, or blame are not.) "
"Do NOT flag mere paraphrase or lexical generalization.\n"
"Judge each code independently; detecting one does not preclude others.\n"
"For each distortion, output one pipe-delimited line:\n"
"CODE | detected(0/1) | licensed(0/1) | target_role | position | valence | evidence\n"
"- licensed: 1 only if detected=1 AND the deviation is licensed by PERSPECTIVE as defined above; "
"0 if detected=1 and not licensed; na if detected=0\n"
"- target_role: perpetrator / victim / neutral / na\n"
"- position: lead / body / na\n"
"- valence: mitigate / amplify / neutral\n"
"- evidence: brief source->retelling, empty if not detected\n"
"Output exactly 6 lines (AR,RI,AS,CD,SO,IJ), no header."
)

HEADER = ["item_id", "url", "task", "gen_model_family", "perspective", "risk_level", "region",
          "compression_ratio", "judge_model", "distortion_code", "detected", "licensed",
          "target_role", "position", "valence", "evidence"]


def parse_judge(text):
    out = {}
    for line in (text or "").replace("```", "").splitlines():
        if line.count("|") < 6:
            continue
        p = [x.strip() for x in line.split("|")]
        if len(p) < 7:
            continue
        code = p[0].upper()
        if code not in CODES:
            continue
        try:
            det = int(p[1])
        except Exception:
            det = 1 if p[1].lower() in ("1", "true", "yes") else 0
        lic = p[2].lower()
        lic = "1" if lic in ("1", "true", "yes") else ("0" if lic in ("0", "false", "no") else "na")
        ev = p[6].replace("|", "/").replace("\n", " ")[:400]
        out[code] = (det, lic, p[3].lower(), p[4].lower(), p[5].lower(), ev)
    return out


def run_judging(items, phase_dir, make_client, out_name="tier2.csv",
                budget_calls=10**9, allowed_judges=None, verbose=True):
    """items: dict 리스트 — 필수 키: item_id, url, task, gen_model_family, perspective,
    risk_level, region, compression_ratio, source_body, output_text.
    judge = 생성 family 제외 2개 (leave-one-family-out). 재개형(progress.txt)."""
    os.makedirs(phase_dir, exist_ok=True)
    out_path = os.path.join(phase_dir, out_name)
    prog_path = os.path.join(phase_dir, "progress.txt")
    done = set()
    if os.path.exists(prog_path):
        done = set(open(prog_path).read().split())
    new_file = not os.path.exists(out_path)
    fout = open(out_path, "a", newline="", encoding="utf-8")
    w = csv.writer(fout, delimiter="|")
    if new_file:
        w.writerow(HEADER)
    clients, calls, errors = {}, 0, 0
    for r in items:
        judges = [f for f in JUDGE_FAMILIES if f != r["gen_model_family"]]
        if allowed_judges:
            judges = [f for f in judges if f in allowed_judges]
        for jf in judges:
            key = f"{r['item_id']}::{jf}"
            if key in done:
                continue
            if calls >= budget_calls:
                fout.close()
                print(f"[budget] {calls} calls done this run; resume later.")
                return calls, errors
            if jf not in clients:
                clients[jf] = make_client(jf, temperature=0.0)
            user = (f"PERSPECTIVE: {r['perspective']}\n\n=== SOURCE ARTICLE ===\n"
                    f"{str(r['source_body'])[:6000]}\n\n=== RETELLING ===\n"
                    f"{str(r['output_text'])[:6000]}")
            try:
                out = clients[jf].generate(user, system=SYS_JUDGE_NARR)
                resp = out[0] if isinstance(out, tuple) else out
            except Exception as e:
                errors += 1
                print(f"[ERR] {key}: {type(e).__name__} {str(e)[:100]}")
                continue
            parsed = parse_judge(resp)
            if len(parsed) < 6 and verbose:
                print(f"[parse<6] {key}: {len(parsed)}/6")
            for code in CODES:
                det, lic, role, pos, val, ev = parsed.get(
                    code, (0, "na", "na", "na", "na", "PARSE_FAIL"))
                w.writerow([r["item_id"], r["url"], r["task"], r["gen_model_family"],
                            r["perspective"], r["risk_level"], r["region"],
                            r.get("compression_ratio", ""), jf, code, det, lic,
                            role, pos, val, ev])
            fout.flush()
            open(prog_path, "a").write(key + "\n")
            done.add(key)
            calls += 1
            if verbose and calls % 25 == 0:
                print(f"  ...{calls} calls (errors {errors})")
    fout.close()
    print(f"[done] calls={calls} errors={errors}")
    return calls, errors
