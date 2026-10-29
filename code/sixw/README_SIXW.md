# sixw: rule-based five-Ws-and-how extractors

The same extractors run over sources, summaries and stories to measure how each axis of an event description (who, whom, what, why, source, when, where, how) is retained or newly introduced. No model judgment and no API calls are involved (spaCy only), so these indicators are independent of the six-type judgments.

## Files

| File | Role |
|---|---|
| `phase0a_extractors_legacy.py` | Original extractors for agents and patients (SRL), attribution and causal connectives, unchanged |
| `sixw_extractors.py` | Re-exports the above and adds time (when), place (where) and manner/instrument (how) extractors (spaCy NER plus patterns) |
| `run_sixw_extract.py` | Runs the extractors over the three layers; resumable |
| `run_sixw_aggregate.py` | Retention, novelty and per-100-word density by axis, with breakdowns and a report |
| `run_refusal_reason.py` | Rule-based reason labels for declined requests (`reason_label` in `data/outputs_declined.csv`) |
| `run_cr_neutral.py` | Contradiction-rate audit runner (same as `prompts/cr_audit_source.py`) |

## Run

```bash
pip install spacy
python -m spacy download en_core_web_sm

python collect.py                 # from the repository root: rebuild article bodies
python code/prepare_inputs.py     # writes code/data/ inputs from the release CSVs

cd code/sixw
python run_sixw_extract.py --layer all --limit 200   # smoke test
python run_sixw_extract.py --layer all --batch 32
python run_sixw_aggregate.py
```

Inputs are read from `code/data/` (`master_articles_2000.csv`, `master_summaries.csv`, `master_news_narrative_v2.csv`); outputs go to `code/sixw/sixw_out/`. The full run (about 5,900 documents) takes from tens of minutes to two hours on CPU. Use `--procs 2` on a two-core machine. Runs can be interrupted and resumed.

## Reading the numbers

* Matching is string-based, so different expressions for the same referent ("the army" and "soldiers") are not linked. Retention is underestimated and novelty overestimated.
* Newly introduced relative time is not a distortion by itself; narration may legitimately construct its own timeline.
* Compare axes only on paired articles, where both summary and story exist.
* Keep these indicators separate from the six-type judgments; do not combine them in one table.
