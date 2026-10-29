# Narrators

Twelve roles, grouped by relation to the event.

| Group | Narrators |
|---|---|
| Third-party observers and helpers | Neutral Observer, Rescuer, Neighbor, Historian, Witness |
| Perpetrator | Perpetrator |
| Victim side | Victim, Survivor, Descendant, Bereaved family |
| Professional accountability roles | Journalist, Investigator |

## Assignment
Articles are shuffled with seed 42, then model family and narrator are rotated jointly so that each of the three families and each of the twelve narrators is balanced across the corpus. Each article receives exactly one (family, narrator) pair. The rotation is implemented in `run_phase0b_neutral_generate.py`.
