from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from vic_rego_estimator.models.schemas import ToolEnvelope
from vic_rego_estimator.scraping.parser import scrape_fee_snapshot
from vic_rego_estimator.storage.snapshot_store import SnapshotStore, fallback_snapshot
from vic_rego_estimator.tools.estimator import estimate_registration_cost
from vic_rego_estimator.tools.normalize import normalize_vehicle_request


@dataclass
class ToolDef:
    name: str
    description: str
    input_schema: dict[str, Any]
    annotations: dict[str, Any]
    security_schemes: list[dict[str, Any]]
    handler: Callable[[dict[str, Any]], Any]


store = SnapshotStore()


async def _get_snapshot(_: dict[str, Any]) -> ToolEnvelope:
    snapshot = store.load()
    freshness = "cached"
    if snapshot is None:
        try:
            snapshot = await scrape_fee_snapshot()
            store.save(snapshot)
            freshness = "refreshed"
        except Exception:
            snapshot = fallback_snapshot()
            freshness = "fallback"

    return ToolEnvelope(
        content=f"Loaded VIC fee snapshot ({freshness}) refreshed {snapshot.refreshed_at.date().isoformat()}.",
        structuredContent={"snapshot": snapshot.model_dump(mode="json")},
        meta=_meta(freshness, snapshot.refreshed_at),
    )


async def _normalize(payload: dict[str, Any]) -> ToolEnvelope:
    normalized = normalize_vehicle_request(payload)
    return ToolEnvelope(
        content=f"Normalized request for {normalized.vehicle_category} {normalized.transaction_type}.",
        structuredContent={"normalizedRequest": normalized.model_dump(mode="json")},
        meta=_meta("n/a", datetime.now(timezone.utc)),
    )


async def _estimate(payload: dict[str, Any]) -> ToolEnvelope:
    normalized = normalize_vehicle_request(payload)
    snapshot = store.load() or fallback_snapshot()
    result = estimate_registration_cost(normalized, snapshot)
    summary = f"Estimated VIC cost {result.total_min:.2f}-{result.total_max:.2f} AUD ({result.confidence} confidence)."
    return ToolEnvelope(
        content=summary,
        structuredContent={"estimate": result.model_dump(mode="json")},
        meta=_meta("snapshot", result.last_refresh),
    )


async def _assumptions(payload: dict[str, Any]) -> ToolEnvelope:
    normalized = normalize_vehicle_request(payload)
    confidence = "low" if normalized.unknown_fields else "high"
    return ToolEnvelope(
        content=f"Generated assumptions with {confidence} confidence.",
        structuredContent={
            "assumptions": normalized.assumptions,
            "unknownFields": normalized.unknown_fields,
            "confidence": confidence,
        },
        meta=_meta("n/a", datetime.now(timezone.utc)),
    )


def _meta(freshness: str, refreshed_at: datetime) -> dict[str, Any]:
    return {
        "openai_output_template": "ui://widget/index.html",
        "widgetDescription": "Vic Rego Estimator widget with form, itemised fee breakdown, confidence and assumptions.",
        "data_freshness": {
            "status": freshness,
            "last_refresh": refreshed_at.isoformat(),
            "refresh_policy": "monthly",
        },
    }


TOOLS: dict[str, ToolDef] = {
    "normalize_vehicle_request": ToolDef(
        name="normalize_vehicle_request",
        description="Normalize user vehicle request and infer missing fields.",
        input_schema={"type": "object", "required": ["transaction_type", "vehicle_category"]},
        annotations={"readOnlyHint": True},
        security_schemes=[{"type": "noauth"}],
        handler=_normalize,
    ),
    "get_fee_snapshot": ToolDef(
        name="get_fee_snapshot",
        description="Load latest scraped fee snapshot from Blob storage with fallback.",
        input_schema={"type": "object", "properties": {}},
        annotations={"readOnlyHint": True},
        security_schemes=[{"type": "noauth"}],
        handler=_get_snapshot,
    ),
    "estimate_registration_cost": ToolDef(
        name="estimate_registration_cost",
        description="Estimate itemised Victorian vehicle registration costs.",
        input_schema={"type": "object", "required": ["transaction_type", "vehicle_category"]},
        annotations={"readOnlyHint": True},
        security_schemes=[{"type": "noauth"}],
        handler=_estimate,
    ),
    "explain_assumptions": ToolDef(
        name="explain_assumptions",
        description="Explain assumptions and uncertainty from unknown inputs.",
        input_schema={"type": "object", "required": ["transaction_type", "vehicle_category"]},
        annotations={"readOnlyHint": True},
        security_schemes=[{"type": "noauth"}],
        handler=_assumptions,
    ),
}
