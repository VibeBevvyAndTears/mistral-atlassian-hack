"""Business logic for deterministic evaluation regressions."""

from __future__ import annotations

import uuid
from typing import Any, cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import inspect, text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from src.eval import repository
from src.eval.models import (
    EvalMetric,
    EvalRunResponse,
    GoldenExample,
    GoldenExampleCreate,
    GoldenExampleResponse,
    GoldenExampleUpdate,
    GoldenKind,
)

THRESHOLDS = {
    "conflict_precision": 0.80,
    "judge_agreement": 0.90,
    "first_pass_fidelity": 0.90,
}
KIND_TO_METRIC = {
    "conflict": "conflict_precision",
    "judge": "judge_agreement",
    "fidelity": "first_pass_fidelity",
}


def _response(row: GoldenExample) -> GoldenExampleResponse:
    return GoldenExampleResponse(
        id=str(row.id),
        org_id=str(row.org_id),
        kind=cast(GoldenKind, row.kind),
        input_json=dict(row.input_json),
        expected_json=dict(row.expected_json),
        notes=row.notes,
        created_at=row.created_at,
    )


def _observed(payload: dict[str, Any]) -> Any:
    for key in ("actual", "output", "prediction"):
        if key in payload:
            return payload[key]
    return None


def evaluate_payloads(goldens: list[dict[str, Any]]) -> EvalRunResponse:
    """Score embedded observed outputs against expected outputs.

    A golden's ``input_json`` may carry an ``actual``, ``output``, or
    ``prediction`` field. This keeps the regression gate deterministic and
    offline while allowing production jobs to persist model outputs.
    """
    if not goldens:
        return EvalRunResponse(
            status="skipped",
            warning="no goldens — skip",
            total_goldens=0,
            metrics={
                name: EvalMetric(
                    value=None, threshold=threshold, passed=True, sample_count=0
                )
                for name, threshold in THRESHOLDS.items()
            },
        )

    scores: dict[str, list[bool]] = {name: [] for name in THRESHOLDS}
    conflict_labels: list[tuple[bool, bool]] = []
    for golden in goldens:
        metric_name = KIND_TO_METRIC.get(str(golden.get("kind")))
        if metric_name is None:
            continue
        observed = _observed(dict(golden.get("input_json") or {}))
        expected = golden.get("expected_json")
        if (
            metric_name == "conflict_precision"
            and isinstance(observed, dict)
            and isinstance(expected, dict)
            and isinstance(observed.get("is_conflict"), bool)
            and isinstance(expected.get("is_conflict"), bool)
        ):
            conflict_labels.append((observed["is_conflict"], expected["is_conflict"]))
            continue
        scores[metric_name].append(observed == expected)

    metrics: dict[str, EvalMetric] = {}
    for name, threshold in THRESHOLDS.items():
        samples = scores[name]
        value: float | None
        if name == "conflict_precision" and conflict_labels:
            predicted_positive = sum(predicted for predicted, _ in conflict_labels)
            true_positive = sum(
                predicted and expected for predicted, expected in conflict_labels
            )
            value = true_positive / predicted_positive if predicted_positive else 0.0
            sample_count = len(conflict_labels)
        else:
            value = sum(samples) / len(samples) if samples else None
            sample_count = len(samples)
        metrics[name] = EvalMetric(
            value=value,
            threshold=threshold,
            passed=value is not None and value > threshold,
            sample_count=sample_count,
        )
    return EvalRunResponse(
        status=(
            "passed" if all(metric.passed for metric in metrics.values()) else "failed"
        ),
        total_goldens=len(goldens),
        metrics=metrics,
    )


async def list_goldens(db: AsyncSession, org_id: UUID) -> list[GoldenExampleResponse]:
    return [_response(row) for row in await repository.list_goldens(db, org_id)]


async def create_golden(
    db: AsyncSession, org_id: UUID, body: GoldenExampleCreate
) -> GoldenExampleResponse:
    row = GoldenExample(
        id=uuid.uuid4(),
        org_id=org_id,
        kind=body.kind,
        input_json=body.input_json,
        expected_json=body.expected_json,
        notes=body.notes,
    )
    return _response(await repository.create_golden(db, row))


async def update_golden(
    db: AsyncSession, org_id: UUID, golden_id: UUID, body: GoldenExampleUpdate
) -> GoldenExampleResponse:
    row = await repository.get_golden(db, org_id, golden_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Golden not found"
        )
    for field in body.model_fields_set:
        setattr(row, field, getattr(body, field))
    await db.flush()
    await db.refresh(row)
    return _response(row)


async def delete_golden(db: AsyncSession, org_id: UUID, golden_id: UUID) -> None:
    row = await repository.get_golden(db, org_id, golden_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Golden not found"
        )
    await repository.delete_golden(db, row)


async def run_regression(db: AsyncSession, org_id: UUID) -> EvalRunResponse:
    rows = await repository.list_goldens(db, org_id)
    return evaluate_payloads(
        [
            {
                "kind": row.kind,
                "input_json": row.input_json,
                "expected_json": row.expected_json,
            }
            for row in rows
        ]
    )


async def override_golden(
    db: AsyncSession, org_id: UUID, golden_id: UUID, human_override: bool
) -> GoldenExampleResponse:
    row = await repository.get_golden(db, org_id, golden_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Golden not found"
        )
    row.expected_json = {
        **row.expected_json,
        "human_override": human_override,
    }
    await db.flush()
    await db.refresh(row)
    return _response(row)


async def override_verdict(
    db: AsyncSession, org_id: UUID, verdict_id: UUID, human_override: bool
) -> dict[str, Any]:
    def _supports_override(sync_connection: Any) -> bool:
        inspector = inspect(sync_connection)
        if "judge_verdicts" not in inspector.get_table_names():
            return False
        return "human_override" in {
            column["name"] for column in inspector.get_columns("judge_verdicts")
        }

    connection = await db.connection()
    if not await connection.run_sync(_supports_override):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verdict overrides unavailable",
        )
    result = await db.execute(
        text(
            "UPDATE judge_verdicts SET human_override = :human_override "
            "WHERE id = :verdict_id AND org_id = :org_id"
        ),
        {
            "human_override": human_override,
            "verdict_id": str(verdict_id),
            "org_id": str(org_id),
        },
    )
    if cast(CursorResult[Any], result).rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Verdict not found"
        )
    return {
        "id": str(verdict_id),
        "org_id": str(org_id),
        "human_override": human_override,
    }
