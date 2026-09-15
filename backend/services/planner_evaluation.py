"""Lightweight measurable planner-quality checks."""
from __future__ import annotations


def evaluate_plan(plan: dict) -> dict:
    candidates = plan.get("candidates") or []
    operations = plan.get("operations") or []
    if not operations:
        return {
            "operation_count": 0,
            "selected_duration_sec": 0.0,
            "average_highlight_score": 0.0,
            "hook_present": False,
            "payoff_present": False,
            "all_operations_grounded": True,
        }

    selected_duration_sec = 0.0
    grounded = True
    scores: list[float] = []
    roles: list[str] = []

    candidate_keys = {
        (item["asset_id"], item["unit_index"])
        for item in candidates
    }
    for operation in operations:
        payload = operation.get("payload") or {}
        metadata = payload.get("metadata") or {}
        selected_duration_sec += float(payload.get("duration", 0)) / 1000.0
        scores.append(float(metadata.get("highlight_score", 0.0)))
        roles.append(str(metadata.get("narrative_role") or ""))
        key = (
            payload.get("asset_id"),
            metadata.get("source_unit_index"),
        )
        if key not in candidate_keys:
            grounded = False

    return {
        "operation_count": len(operations),
        "selected_duration_sec": round(selected_duration_sec, 3),
        "average_highlight_score": (
            round(sum(scores) / len(scores), 4) if scores else 0.0
        ),
        "hook_present": "hook" in roles,
        "payoff_present": "payoff" in roles,
        "all_operations_grounded": grounded,
    }
