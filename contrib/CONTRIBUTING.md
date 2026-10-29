# Contributing to ReTold-2k

The files in `data/` are frozen at the counts printed in the paper; `verify.py` asserts them. Everything that is incomplete or missing has a keyed, empty slot in this folder. Fill a slot, run `python verify.py --contrib`, and open a pull request. Filled slots are never merged into `data/`; they are published next to it as a versioned addition.

## Slots

| File | Rows | What is missing | How to fill |
|---|---|---|---|
| `judgments_missing.csv` | 264 | 108 rows: 18 outputs (3 stories, 15 summaries) where the Gemini judge call failed. 84 rows: 7 summaries that exist but were never judged. 72 rows: 6 summaries that do not exist yet (see next file). | Run the judge in `code/judge_core.py` with `prompts/judging.txt`, temperature 0. Fill `detected, licensed, target_role, position, valence, evidence`; set `judge_model` to the exact model id you used (the original Gemini 3.1 Flash-Lite preview was retired on 2026-05-25, so these rows will carry a successor model and must be reported as such). |
| `outputs_summary_missing.csv` | 13 | 7 summaries with text that the refusal heuristic flagged at generation time (`status = generated_not_judged`): decide whether each is a summary or a refusal. 6 slots with no usable output (`status = to_generate`): one article never summarized by any family, three Gemini outputs that came back empty. | Generate with `prompts/generation_summary.txt`, `target_words = round(source_words x 0.55)`, no system prompt. Paste the text into `output_text`, set `n_words`, `source_words`, and `status = generated`. Then judge it via `judgments_missing.csv`. |
| `cr_audit_per_story.csv` | 1,926 | Filled: the contradiction-rate audit of every story as run (claude-haiku-4-5-20251001). Contributions here are re-audits with other models, added as new rows with their own `audit_model`. | `python contrib/run_cr_audit_all.py` after `collect.py`, writing to a copy of the file. |
| `labels_template.csv` | 911 | Human labels exist for 50 of the 911 contested judgments (all 18 legitimacy splits, 32 of the 893 detection splits; `already_labelled_by_authors`). | Copy the file, set `annotator` to a new code (A4, A5, ...; never a name), label with the same scheme as `data/author_labels_50.csv`: `1` distortion present and unwarranted, `0` present but warranted by the narrator, `-1` no distortion. The two judges' verdicts are shown so you can see what they split on; label from the story and the article, not from the judges. |
| `url_alternates.csv` | 1 (example) | Alternative locations for articles whose URL no longer resolves. | Add a row per article: `alternate_kind` is `archive` (web.archive.org, archive.today), `syndicated` (same text on another site) or `moved`. Delete the example row. Never paste article text. |
| `notebooks/` | | The notebook that generated the Low/Medium/High stories and the notebook that generated the summaries are not in this repository. | See `notebooks/README.md` for what each must contain to be accepted. |

## Rules

* Article text never enters this repository, in any file. `verify.py --contrib` fails on a `body` column and on cells longer than 12,000 characters in any contrib file except `output_text` of model outputs.
* Prompts are not edited. If you ran a different prompt, you ran a different task; say so in the pull request and do not fill these slots with it.
* One row per `(item_id, distortion_code, judge_model)`; keep the ids exactly as given.
* Annotators and contributors appear as codes, not names.
* Say which model id and date you used for any model-produced cell.
