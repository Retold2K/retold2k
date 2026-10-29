# Notebook slots

Two notebooks that produced released outputs are not in this repository. A contribution is accepted when it is the notebook that was actually run, or a script that reproduces its outputs on a sample and says so.

| Slot | Produced | Must contain |
|---|---|---|
| `generate_story_initial.ipynb` | the 1,445 Low/Medium/High stories in `data/outputs_story.csv` | the prompt in `prompts/generation_story.txt` byte-for-byte; the article shuffle and the joint (family, narrator) rotation; model ids; temperature; the `Y`/`N` prefix handling that produced `data/outputs_declined.csv` |
| `generate_summary.ipynb` | the compression-0.55 summaries in `data/outputs_summary.csv` (and the unreleased 0.4 and 0.7 runs) | the prompt in `prompts/generation_summary.txt` byte-for-byte; `target_words = round(source_words x ratio)`; model ids; temperature; the refusal heuristic that set `refusal_flag` |

`code/run_phase0b_neutral_generate.py` is the generation script for the 481 neutral-severity stories and is the reference for the first slot.
