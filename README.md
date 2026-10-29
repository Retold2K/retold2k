# ReTold-2k

Data and code for *What Breaks When Facts Become Stories? The Distortions Source-Agreement Metrics Miss When Models Retell Real Events* (TAE Workshop @ NeurIPS 2026).

Three model families (OpenAI GPT, Google Gemini, Anthropic Claude) rewrote 1,999 news articles twice: as a summary at compression ratio 0.55 and as a story told by one of twelve assigned narrators. Every output was read by the two families that did not produce it, which judged six distortion types and, for each detection, whether the assigned narrator warranted the change. This bundle releases the outputs, every judgment per judge without aggregation, the 911 contested judgments on which the two judges disagreed, and the individual labels of three authors on fifty of those. Article text is not included; the index lets you rebuild the corpus from the URLs.

## Models

Stories were generated in two runs. The first run (Low, Medium and High severity articles) used gpt-4o-mini, gemini-2.0-flash and claude-haiku-4-5; the second run (neutral-severity articles) used gpt-5.4-mini, gemini-3.1-flash-lite and claude-haiku-4-5. The exact generator of every story is in the `gen_model` column of `outputs_story.csv` and `outputs_declined.csv`. Summaries and all judgments were produced with the current models of the three families (GPT-5.4 mini, Gemini 3.x Flash, Claude Haiku 4.5); `code/common_utils.py` holds the model identifiers used by the judging pipeline. Compare generators only within a run.

## Contents

```
data/
  articles_index.csv      1,999 rows   one per article: URL, date, region, severity, title. No body.
  outputs_story.csv       1,926 rows   one per story (article x assigned family x assigned narrator)
  outputs_declined.csv       73 rows   requests the model declined, with its reply and a reason label
  outputs_summary.csv     5,984 rows   compression-0.55 summaries from all three families, judged
  judgments.csv          94,812 rows   one per (output, distortion type, judge); 23,094 story + 71,718 summary
  contested_911.csv       1,822 rows   the 911 (story, type) judgments where the two judges disagreed, both rows
  author_labels_50.csv      150 rows   50 contested judgments x 3 authors, kept individual
prompts/
  generation_story.txt, generation_summary.txt, judging.txt   verbatim, as run
  cr_audit_source.py                                          contradiction-rate audit, prompt embedded
  README.txt                                                  placeholders and user-turn template
code/
  judge_core.py, run_phase1_narrator_judge.py, run_phase1b_neutral_judge.py   the judging pipeline
  run_phase0b_neutral_generate.py                                             story generation and narrator assignment
  run_phase3_aggregate.py, common_utils.py                                    aggregation, API clients
  sixw/                                                                       rule-based extractors (Table 3)
  narrators.md                                                                twelve narrators and their groups
  prepare_inputs.py                                                           release CSVs -> pipeline inputs
collect.py     rebuilds the article corpus from the index (Event Registry or direct fetch)
score.py       reproduces the paper's tables from data/; scores a detector per judge
verify.py      integrity checks; every count asserted is the count in the paper
```

## Quick start

```bash
python verify.py          # row counts, id consistency, no article text, no names
python score.py           # Tables 4, 5, A1, A2, licensing share, refusals, from data/ alone
```

`score.py` needs only the standard library and reproduces the paper's numbers to the printed precision (three cells of Table A1 differ by 0.1 from rounding).

## Where each number in the paper comes from

| Paper | File(s) | How |
|---|---|---|
| Section 3 corpus (1,999 articles; 1,926 stories; 73 declined; 1,923 paired) | `articles_index`, `outputs_story`, `outputs_declined`, `outputs_summary` | paired = story and 0.55 summary from the same family |
| Table 3, rule-based indicators | `code/sixw/` on the rebuilt corpus | run `collect.py`, then `code/prepare_inputs.py`, then the sixw scripts |
| Table 4, Figure 2, Table A1 | `judgments.csv` | `score.py` |
| Table 5, judge disagreement | `judgments.csv` | `score.py` |
| Figure 3, Table A2, direction | `judgments.csv` (`target_role`, `valence`) | `score.py` |
| Table 6, author labels | `author_labels_50.csv` | kappa and splits per the paper's Appendix |
| Section 5 refusals (41 / 23 / 6 / 3) | `outputs_declined.csv` (`reason_label`) | `score.py` |
| Blind spot (contradiction-free stories that still carry accountability distortion) | `prompts/cr_audit_source.py` on `outputs_story.csv` + rebuilt corpus | audit must be rerun; its per-story output is not released |

## Columns

Identifiers. A story is `ST_{family}_{article_id}_{Narrator}`; a summary is `SUM_{family}_{article_id}_055`. `judgments.item_id` and `contested_911.item_id` point to `outputs_story.gen_id` or `outputs_summary.gen_id`. `article_id` joins everything to `articles_index`.

`judgments.csv`: `item_id, task (story|summary), article_id, url, gen_model_family, perspective, compression_ratio, risk_level, region, judge_model, distortion_code, detected, licensed, target_role, position, valence, evidence`.

* `distortion_code`: AR Vanishing Actor, RI Role Reversal, CD Causal Fading (accountability); AS Claim Laundering, SO Selective Omission, IJ Invented Addition (surface). Codes are the judge-prompt names; the paper's names are in parentheses in `score.py`.
* `detected` 0/1 by that judge. `licensed` 1 if the judge found the deviation warranted by the assigned narrator, 0 if not, `na` if not detected. Summaries have no narrator, so `licensed` is 0 whenever detected (the prompt says so); this makes the summary condition the conservative comparison.
* An *unwarranted detection* is `detected == 1 and licensed == 0`. Every rate in the paper's story columns uses this unless marked "all".
* `target_role` (perpetrator / victim / neutral / na), `position` (lead / body / na), `valence` (mitigate / amplify / neutral) and `evidence` (the judge's brief source-to-retelling quote) are as the judge wrote them.

`contested_911.csv` has the same columns plus `output_text`. A judgment is contested when the two judges' `(detected, licensed)` pairs differ on an accountability code. 911 judgments over 700 stories. The judges' `evidence` quotes are the source passages the paper refers to; the full article text is not included.

`author_labels_50.csv`: `item_id, distortion_code, kind (detection_split | legitimacy_split), risk_level, perspective, annotator (A1|A2|A3), label, note`. Labels: `1` distortion present and unwarranted, `0` distortion present but warranted by the narrator, `-1` no distortion present, blank = not labelled (one A1 cell). Notes are the annotator's free text in their working language. The three columns are never merged into a gold label; score against each.

`outputs_declined.csv`: `reason_label` is a rule-based cue match (`policy_safety`, `no_such_narrative`, `insufficient_info`, `other_unclassified`) and `matched_cue` the matched string, from `code/sixw/run_refusal_reason.py`.

`outputs_summary.csv`: `n_words`, `source_words` are whitespace word counts; `refusal_flag` is 0 for every released row.

## Scoring a detector

Produce one row per `(item_id, distortion_code)` with `detected` in {0,1} and optionally `licensed`:

```bash
python score.py --detector my_detector.csv
```

This prints precision, recall and F1 against each judge family separately, for accountability and surface codes. Report the three side by side. The paper's argument is that no merged gold label exists for the contested cases, so do not average them into one number. For the 50 author-labelled items, do the same against A1, A2 and A3.

## Evaluating a generator

1. `python collect.py` to rebuild `code/data/master_articles_2000.csv` (see below).
2. Generate stories with `prompts/generation_story.txt` and the assignment rule in `code/run_phase0b_neutral_generate.py` (the script used for the second run; shuffle with seed 42, rotate family and narrator jointly), and summaries with `prompts/generation_summary.txt` at ratio 0.55.
3. Judge with `code/run_phase1_narrator_judge.py` (two judges per output, excluding the generator's family, temperature 0). `code/prepare_inputs.py` shows the input format.
4. Compute rates with the definitions above. Absolute levels move with the judge models, so compare against our per-judge baselines in `judgments.csv`, not against the paper's headline numbers.

## Rebuilding the article corpus

The articles were collected through Event Registry (newsapi.ai). `collect.py` first asks Event Registry for each URL (set `ER_API_KEY`; `pip install eventregistry`), which returns the same body we used whenever the article is still indexed, then falls back to fetching the page directly (`pip install trafilatura`). It writes a log with status and timestamp per article and is resumable. Pages change and disappear; report the size of the corpus you actually rebuilt. Researchers who need the exact text we used for a non-commercial replication can contact the authors.

## Notes on use

* Several generator and judge models (gpt-4o-mini, gemini-2.0-flash, the Gemini 3.1 Flash-Lite preview) have been or may be retired by their providers. Treat outputs and judgments as fixed data rather than something to regenerate exactly.
* Articles come from an English-language news aggregator and were selected by region and topic keywords; severity labels (`risk_level`) are the collection category, not an annotation.
* Per-judge statistics use whatever judges an output has; `score.py` applies the paper's definitions, so run it rather than recomputing from scratch when comparing with the paper.

## Not included, and why

* Article text: copyright. Rebuild it from `articles_index.csv` with `collect.py`.
* Summaries at compression 0.4 and 0.7 and their judgments: the paper's claims do not use them.
* Any mapping from A1/A2/A3 to the authors' identities.

## License

Data and prompts: CC BY-NC 4.0. Code: MIT. Model outputs are additionally subject to the providers' terms. See `LICENSE`.

## Citation

See `CITATION.cff`.
