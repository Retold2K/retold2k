Prompts, verbatim as run. Do not edit them; a changed prompt is a changed task.

generation_story.txt
    {perspective}     one of the twelve narrators in ../code/narrators.md
    {original_story}  article title, a blank line, then the article body (first 6,000 characters)
    One call per article. Second run (neutral-severity articles): temperature 0, family and
    narrator assigned by the rotation in ../code/run_phase0b_neutral_generate.py (shuffle with
    seed 42, then rotate family and narrator jointly). First run (Low/Medium/High): the
    same prompt, run from an earlier notebook (slot: ../contrib/notebooks/README.md); the
    generator of every story is in the gen_model column of ../data/outputs_story.csv.

generation_summary.txt
    {target_words} = round(source word count x compression ratio); the released summaries use 0.55
    {title}, {body}  article title and body
    Task instruction: no system prompt, identical settings for all three families
    (instruction recommended temperature 0.7). The summary-generation notebook has a slot
    in ../contrib/notebooks/README.md.

judging.txt
    System prompt for the judge. The user turn is built in ../code/judge_core.py as:
        PERSPECTIVE: {perspective}

        === SOURCE ARTICLE ===
        {source body, first 6,000 characters}

        === RETELLING ===
        {output text, first 6,000 characters}
    For summaries PERSPECTIVE is "None (faithful summary)". Temperature 0. Two judges per
    output: the two families that did not generate it. Output parsed by parse_judge().

cr_audit_source.py
    The contradiction-rate audit used for the blind-spot analysis (Sections 4-5), prompt embedded.
