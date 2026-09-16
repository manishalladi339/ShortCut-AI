"""Create-With-Me constrained edit proposal and atomic apply endpoints."""
from __future__ import annotations

import copy
import uuid

from fastapi import APIRouter, Depends, HTTPException

from core.deps import get_current_user
from core.security import utc_now
from db.mongo import get_db
from models.constrained_edit import (
    ApplyConstrainedEditRequest,
    ConstrainedEditProposalOut,
    CreateConstrainedEditRequest,
)
from models.project_state import ProjectStateDocument, ProjectStateOut
from routers.project_state import _get_or_create_state
from services.constrained_editing import (
    apply_constrained_operations,
    build_constrained_proposal,
)
from services.creator_memory import refresh_creator_memory

router = APIRouter(prefix="/projects", tags=["constrained-edits"])


def _error(code: str, message: str, status: int = 422) -> HTTPException:
    return HTTPException(
        status_code=status,
        detail={"error": {"code": code, "message": message}},
    )


@router.post(
    "/{project_id}/constrained-edits",
    response_model=ConstrainedEditProposalOut,
)
async def create_constrained_edit(
    project_id: str,
    body: CreateConstrainedEditRequest,
    user: dict = Depends(get_current_user),
) -> ConstrainedEditProposalOut:
    state = await _get_or_create_state(project_id, user["id"])
    try:
        proposal = build_constrained_proposal(
            project_id=project_id,
            user_id=user["id"],
            state=state,
            instruction=body.instruction,
            scope_start_sec=body.scope_start_sec,
            scope_end_sec=body.scope_end_sec,
        )
    except ValueError as exc:
        raise _error("constrained_edit.unsupported_or_empty", str(exc)) from exc

    now = utc_now()
    proposal = {
        "id": str(uuid.uuid4()),
        **proposal,
        "created_at": now,
        "updated_at": now,
        "applied_project_state_version": None,
        "applied_operation_ids": [],
        "skipped_operation_ids": [],
    }
    await get_db().ai_constrained_edit_proposals.insert_one(copy.deepcopy(proposal))
    return ConstrainedEditProposalOut(**proposal)


@router.get(
    "/{project_id}/constrained-edits",
    response_model=list[ConstrainedEditProposalOut],
)
async def list_constrained_edits(
    project_id: str,
    user: dict = Depends(get_current_user),
) -> list[ConstrainedEditProposalOut]:
    # Ownership is enforced by the canonical state lookup.
    await _get_or_create_state(project_id, user["id"])
    docs = await get_db().ai_constrained_edit_proposals.find(
        {"project_id": project_id, "user_id": user["id"]},
        {"_id": 0},
    ).sort("created_at", -1).limit(50).to_list(50)
    return [ConstrainedEditProposalOut(**doc) for doc in docs]


@router.post(
    "/{project_id}/constrained-edits/{proposal_id}/apply",
    response_model=ProjectStateOut,
)
async def apply_constrained_edit(
    project_id: str,
    proposal_id: str,
    body: ApplyConstrainedEditRequest,
    user: dict = Depends(get_current_user),
) -> ProjectStateOut:
    db = get_db()
    proposal = await db.ai_constrained_edit_proposals.find_one(
        {
            "id": proposal_id,
            "project_id": project_id,
            "user_id": user["id"],
            "status": "proposed",
        },
        {"_id": 0},
    )
    if not proposal:
        raise _error("constrained_edit.not_found", "Edit proposal not found", 404)

    state = await _get_or_create_state(project_id, user["id"])
    expected = int(body.expected_version)
    if state["version"] != expected or proposal["project_state_version"] != expected:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "project_state.version_conflict",
                    "message": "Timeline changed after this AI proposal was created",
                    "current_version": state["version"],
                }
            },
        )

    all_operations = proposal.get("operations") or []
    available_ids = {operation["id"] for operation in all_operations}
    selected_ids = (
        list(dict.fromkeys(body.operation_ids))
        if body.operation_ids is not None
        else [operation["id"] for operation in all_operations]
    )
    if any(operation_id not in available_ids for operation_id in selected_ids):
        raise _error(
            "constrained_edit.invalid_operation_selection",
            "One or more selected operations do not belong to this proposal",
        )
    selected = [
        operation for operation in all_operations if operation["id"] in selected_ids
    ]
    if not selected:
        raise _error("constrained_edit.empty_selection", "Select at least one change")

    try:
        candidate = apply_constrained_operations(state=state, operations=selected)
    except ValueError as exc:
        raise _error("constrained_edit.invalid_mutation", str(exc), 409) from exc

    now = utc_now()
    candidate["version"] = state["version"] + 1
    candidate["updated_at"] = now
    candidate = ProjectStateDocument(**candidate).model_dump()

    result = await db.project_states.replace_one(
        {
            "project_id": project_id,
            "user_id": user["id"],
            "version": expected,
        },
        candidate,
    )
    if result.modified_count != 1:
        latest = await db.project_states.find_one(
            {"project_id": project_id, "user_id": user["id"]},
            {"_id": 0, "version": 1},
        )
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "code": "project_state.version_conflict",
                    "message": "Timeline changed while the proposal was being applied",
                    "current_version": (latest or {}).get("version", expected),
                }
            },
        )

    selected_set = set(selected_ids)
    skipped_ids = [
        operation["id"]
        for operation in all_operations
        if operation["id"] not in selected_set
    ]
    await db.edit_operations.insert_one(
        {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "user_id": user["id"],
            "from_version": expected,
            "to_version": candidate["version"],
            "operation": "apply_constrained_ai_edit",
            "payload": {
                "proposal_id": proposal_id,
                "instruction": proposal["instruction"],
                "applied_operation_ids": selected_ids,
                "skipped_operation_ids": skipped_ids,
            },
            "created_at": now,
        }
    )
    await db.project_state_versions.insert_one(
        {
            **copy.deepcopy(candidate),
            "snapshot_created_at": now,
            "operation": f"apply_constrained_ai_edit:{proposal_id}",
        }
    )
    await db.ai_constrained_edit_proposals.update_one(
        {"id": proposal_id, "user_id": user["id"], "status": "proposed"},
        {
            "$set": {
                "status": "applied",
                "applied_project_state_version": candidate["version"],
                "applied_operation_ids": selected_ids,
                "skipped_operation_ids": skipped_ids,
                "updated_at": now,
            }
        },
    )
    await refresh_creator_memory(user_id=user["id"])
    return ProjectStateOut(**candidate)
