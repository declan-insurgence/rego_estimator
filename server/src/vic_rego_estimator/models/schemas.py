from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


TransactionType = Literal["new_registration", "renewal", "transfer"]
VehicleCategory = Literal[
    "passenger_car",
    "motorcycle",
    "light_commercial_ute",
    "heavy_vehicle_truck",
    "trailer",
    "caravan",
    "bus",
]


class VehicleRequest(BaseModel):
    transaction_type: TransactionType
    vehicle_category: VehicleCategory
    make: str | None = None
    model: str | None = None
    year: int | None = None
    body_type: str | None = None
    fuel_type: str | None = None
    tare_kg: float | None = None
    gvm_kg: float | None = None
    seats: int | None = None
    postcode: str | None = None
    suburb: str | None = None
    use_type: Literal["private", "business"] = "private"
    term_months: Literal[3, 6, 12] = 12
    market_value_aud: float | None = None
    concession_flags: dict[str, bool] = Field(default_factory=dict)
    manual_overrides: dict[str, float] = Field(default_factory=dict)


class NormalizedVehicleRequest(VehicleRequest):
    inferred_fields: dict[str, Any] = Field(default_factory=dict)
    unknown_fields: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class FeeLineItem(BaseModel):
    key: str
    label: str
    amount_min: float
    amount_max: float
    source: str
    mandatory: bool = True
    notes: str | None = None


class FeeSnapshot(BaseModel):
    jurisdiction: str = "VIC"
    refreshed_at: datetime
    sources: list[str]
    light_vehicle_fee: dict[str, float]
    tac_charge_by_term: dict[str, float]
    transfer_fee: float
    number_plate_fee: float
    heavy_vehicle_base_fee: dict[str, float]
    duty_rates: list[dict[str, float]]
    concession_rules: dict[str, float]


class EstimateResult(BaseModel):
    transaction_type: TransactionType
    vehicle_category: VehicleCategory
    total_min: float
    total_max: float
    confidence: Literal["high", "medium", "low"]
    confidence_score: float
    line_items: list[FeeLineItem]
    assumptions: list[str]
    concessions_applied: list[str]
    last_refresh: datetime
    source_urls: list[str]


class ToolEnvelope(BaseModel):
    content: str
    structuredContent: dict[str, Any]
    meta: dict[str, Any]
