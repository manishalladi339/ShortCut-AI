"""Lightweight measurable planner-quality checks."""
from __future__ import annotations


def evaluate_plan(plan: dict) -> dict:
    candidates = plan.get("candidates") or []
    operations = plan.get("operations") or []
    candidate_keys = {
        (item["asset_id"], item["unit_index"])
        for item in candidates
    }

    selected_duration_sec = round(
        sum(max(0.0, float(item["end"]) - float(item["start"])) for item in candidates),
        3,
    )
    scores = [float(item.get("final_score", 0.0)) for item in candidates]
    roles = [str(item.get("narrative_role") or "") for item in candidates]

    grounded = True
    for operation in operations:
        if operation.get("operation") != "add_clip":
            continue
        payload = operation.get("payload") or {}
        metadata = payload.get("metadata") or {}
        key = (
            payload.get("asset_id"),
            metadata.get("source_unit_index"),
        )
        if key not in candidate_keys:
            grounded = False

    return {
        "operation_count": len(operations),
        "selected_duration_sec": selected_duration_sec,
        "average_highlight_score": (
            round(sum(scores) / len(scores), 4) if scores else 0.0
        ),
        "hook_present": "hook" in roles,
        "payoff_present": "payoff" in roles,
        "all_operations_grounded": grounded,
        "candidate_count": len(candidates),
    }
