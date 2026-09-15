"""Human-review helpers for applying AI edit-plan operations safely."""
from __future__ import annotations

import uuid


class PlanReviewError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def assign_operation_ids(operations: list[dict]) -> list[dict]:
    """Ensure newly generated operations have stable IDs inside their plan."""
    seen: set[str] = set()
    for operation in operations:
        operation_id = str(operation.get("id") or "").strip()
        if not operation_id or operation_id in seen:
            operation_id = str(uuid.uuid4())
            operation["id"] = operation_id
        seen.add(operation_id)
    return operations


def select_reviewed_operations(
    operations: list[dict],
    requested_ids: list[str] | None,
) -> tuple[list[dict], list[str], list[str]]:
    """Select reviewed operations while preserving the canonical primary story.

    Granular review may omit optional B-roll/caption operations. Primary
    add_clip operations are treated as one atomic story/timing group because
    captions and overlays are positioned against that output timeline.
    """
    if requested_ids is None:
        ids = [
            str(operation.get("id"))
            for operation in operations
            if operation.get("id")
        ]
        return list(operations), ids, []

    if len(requested_ids) != len(set(requested_ids)):
        raise PlanReviewError(
            "planner.duplicate_operation_selection",
            "Operation selection contains duplicate IDs",
        )

    if any(not operation.get("id") for operation in operations):
        raise PlanReviewError(
            "planner.plan_not_reviewable",
            "This older AI plan has no operation IDs; regenerate it for granular review",
        )

    by_id = {str(operation["id"]): operation for operation in operations}
    unknown = sorted(set(requested_ids) - set(by_id))
    if unknown:
        raise PlanReviewError(
            "planner.unknown_operation_selection",
            f"Selected operation IDs are not part of this plan: {', '.join(unknown)}",
        )

    selected_set = set(requested_ids)
    primary_ids = {
        str(operation["id"])
        for operation in operations
        if operation.get("operation") == "add_clip"
    }
    if primary_ids and not primary_ids.issubset(selected_set):
        raise PlanReviewError(
            "planner.primary_story_partial_selection",
            "Primary story clips must be applied together; review B-roll and captions individually",
        )

    selected = [
        operation
        for operation in operations
        if str(operation["id"]) in selected_set
    ]
    applied_ids = [str(operation["id"]) for operation in selected]
    skipped_ids = [
        str(operation["id"])
        for operation in operations
        if str(operation["id"]) not in selected_set
    ]
    return selected, applied_ids, skipped_ids
