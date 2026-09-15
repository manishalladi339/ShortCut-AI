"""Conservative speaker-turn pacing for an already-grounded narrative order."""
from __future__ import annotations


def rebalance_speaker_runs(
    items: list[dict], *, max_same_speaker_run: int
) -> list[dict]:
    """Break long same-speaker runs using only safe body-to-body swaps.

    Hook and payoff positions are preserved. Unknown/multi-speaker candidates
    are not treated as a known speaker for run limiting.
    """
    if max_same_speaker_run < 1 or len(items) < 3:
        return list(items)

    result = list(items)
    run_speaker: str | None = None
    run_length = 0

    for index, current in enumerate(result):
        speaker = current.get("primary_speaker")
        if not speaker:
            run_speaker = None
            run_length = 0
            continue

        if speaker == run_speaker:
            run_length += 1
        else:
            run_speaker = speaker
            run_length = 1

        if run_length <= max_same_speaker_run:
            continue
        if current.get("narrative_role") != "body":
            continue

        swap_index: int | None = None
        for candidate_index in range(index + 1, len(result)):
            alternative = result[candidate_index]
            alt_speaker = alternative.get("primary_speaker")
            if (
                alternative.get("narrative_role") == "body"
                and alt_speaker
                and alt_speaker != speaker
            ):
                swap_index = candidate_index
                break

        if swap_index is None:
            continue

        result[index], result[swap_index] = result[swap_index], result[index]
        result[index].setdefault("reasons", []).append(
            "speaker-turn pacing reorder"
        )
        run_speaker = result[index].get("primary_speaker")
        run_length = 1

    return result
