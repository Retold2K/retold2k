# -*- coding: utf-8 -*-
"""Phase 0b — Neutral 기사 498건 관점 서술 신규 생성.
'Perspective Narrative Agent' 프롬프트 그대로 (Y/N 프리픽스 규약 동일).
배정: seed 42, 3계열 × 12화자 균형 순환 (기사당 1계열·1화자 — 기존 코어와 동일 설계).
재개형: progress_gen.txt. 스모크: 환경변수 SMOKE=1 → 6건만.
출력: phase0b_neutral_generation/neutral_narratives.csv (master_news_narrative 스키마)
"""
import os, csv, random, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from common_utils import ROOT, make_client, clean
import pandas as pd

GEN_PROMPT = '''You are a "Perspective Narrative Agent".

GOAL:
Rewrite the following historical story from the specific perspective of a "{perspective}".

ORIGINAL STORY:
<<<
{original_story}
>>>

CONDITION:
1. POV: Use the voice and emotional tone of a "{perspective}".
2. Timeline: Start the story with the "YYYY-MM" format based on the source's date.
3. Length: Approximately 200 words.
4. Prefix:
   - Start with "Y" if you can successfully rewrite it into a story.
   - Start with "N" if the source content is insufficient to create a 200-word story.

CONSTRAINTS:
- If "Y": Output format must be: Y \\n [YYYY-MM], [Rewritten Story]
- If "N": Output format must be: N \\n [Reason]
- Maintain chronological order and do not invent facts.
- The style should be vivid enough to be illustrated in 4 storyboard images.

Output:
'''

PERSPECTIVES = ["Neutral Observer", "Witness", "Victim", "Perpetrator", "Survivor",
                "Bereaved family", "Rescuer", "Neighbor", "Journalist",
                "Investigator", "Historian", "Descendant"]
FAMILIES = ["gpt", "claude", "gemini"]
HEADER = ["gen_id", "task", "article_id", "url", "original_row_index",
          "gen_model_family", "gen_model_label_raw", "perspective",
          "is_possible", "output_text"]

def main():
    smoke = os.environ.get("SMOKE") == "1"
    out_dir = os.path.join(ROOT, "phase0b_neutral_generation")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "neutral_narratives.csv")
    prog_path = os.path.join(out_dir, "progress_gen.txt")

    a = pd.read_csv(os.path.join(ROOT, "data", "master_articles_2000.csv"))
    neu = a[(a.risk_level == "Neutral") & (a.has_narrator != True)].copy()
    neu = neu.sort_values("article_id").reset_index(drop=True)
    print(f"Neutral 대상: {len(neu)}")

    # 배정: seed 42 셔플 후 (계열, 화자) 균형 순환 → 계열별 ~166, 화자별 ~41~42
    rng = random.Random(42)
    idx = list(range(len(neu)))
    rng.shuffle(idx)
    assign = {}
    for k, i in enumerate(idx):
        assign[neu.loc[i, "article_id"]] = (FAMILIES[k % 3], PERSPECTIVES[k % 12])

    done = set()
    if os.path.exists(prog_path):
        done = set(open(prog_path).read().split())
    new_file = not os.path.exists(out_path)
    fout = open(out_path, "a", newline="", encoding="utf-8")
    w = csv.writer(fout, delimiter="|")
    if new_file:
        w.writerow(HEADER)

    clients, calls, errors = {}, 0, 0
    limit = 6 if smoke else 10**9
    for _, r in neu.iterrows():
        aid = r["article_id"]
        if aid in done:
            continue
        if calls >= limit:
            break
        fam, persp = assign[aid]
        if fam not in clients:
            clients[fam] = make_client(fam, temperature=0.0)
        story = clean(str(r["title"])) + "\n\n" + str(r["body"])[:6000]
        prompt = GEN_PROMPT.format(perspective=persp, original_story=story)
        try:
            out = clients[fam].generate(prompt)
            text = out[0] if isinstance(out, tuple) else out
        except Exception as e:
            errors += 1
            print(f"[ERR] {aid} ({fam}/{persp}): {type(e).__name__} {str(e)[:100]}")
            continue
        head = (text or "").strip()[:1]
        is_possible = "Y" if head.upper() == "Y" else ("N" if head.upper() == "N" else "?")
        gen_id = f"NNneu_{fam}_{aid}_{persp.replace(' ', '')}"
        w.writerow([gen_id, "news_narrative_neutral", aid, r["url"], "",
                    fam, f"{fam}:MODEL_REGISTRY-2026-07", persp,
                    is_possible, clean(text)[:12000]])
        fout.flush()
        open(prog_path, "a").write(str(aid) + "\n")
        done.add(aid)
        calls += 1
        if calls % 25 == 0:
            print(f"  ...{calls} generated (errors {errors})")
    fout.close()
    print(f"[done] generated={calls} errors={errors} -> {out_path}")

if __name__ == "__main__":
    main()
