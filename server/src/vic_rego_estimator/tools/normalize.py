from __future__ import annotations

import logging

from vic_rego_estimator.models.schemas import NormalizedVehicleRequest, VehicleRequest

logger = logging.getLogger("vic_rego_estimator.normalize")

CATEGORY_DEFAULTS = {
    "passenger_car": {"body_type": "sedan", "tare_kg": 1500, "seats": 5},
    "motorcycle": {"body_type": "motorcycle", "tare_kg": 220, "seats": 2},
    "light_commercial_ute": {"body_type": "ute", "tare_kg": 2100, "seats": 2},
    "heavy_vehicle_truck": {"body_type": "truck", "gvm_kg": 12000, "seats": 2},
    "trailer": {"body_type": "trailer", "tare_kg": 750, "seats": 0},
    "caravan": {"body_type": "caravan", "tare_kg": 2000, "seats": 0},
    "bus": {"body_type": "bus", "gvm_kg": 8000, "seats": 20},
}


CONCESSION_HINTS = {
    "pensioner": "Pensioner concession may reduce registration components for eligible private vehicles.",
    "veteran": "Eligible veterans may receive fee reductions depending on vehicle class.",
    "primary_producer": "Primary producer concessions may apply for qualifying business-use vehicles.",
}


def normalize_vehicle_request(payload: dict) -> NormalizedVehicleRequest:
    try:
        req = VehicleRequest.model_validate(payload)
        inferred_fields: dict[str, object] = {}
        assumptions: list[str] = []
        unknown_fields: list[str] = []

        defaults = CATEGORY_DEFAULTS[req.vehicle_category]
        data = req.model_dump()

        for field_name, default_value in defaults.items():
            if data.get(field_name) is None:
                data[field_name] = default_value
                inferred_fields[field_name] = default_value
                assumptions.append(f"Defaulted {field_name} to {default_value} based on vehicle category.")

        if not req.postcode and not req.suburb:
            unknown_fields.append("postcode_or_suburb")
            assumptions.append("Geographic rating zone unknown; used metro baseline and widened TAC range.")

        if req.transaction_type == "transfer" and req.market_value_aud is None:
            unknown_fields.append("market_value_aud")
            assumptions.append("Market value unknown; motor vehicle duty estimated as a range.")

        for flag, enabled in req.concession_flags.items():
            if enabled and flag in CONCESSION_HINTS:
                assumptions.append(CONCESSION_HINTS[flag])

        for required in ["make", "model", "year", "fuel_type"]:
            if data.get(required) is None:
                unknown_fields.append(required)

        return NormalizedVehicleRequest(
            **data,
            inferred_fields=inferred_fields,
            unknown_fields=sorted(set(unknown_fields)),
            assumptions=assumptions,
        )
    except Exception as exc:
        logger.exception("normalize_vehicle_request_failed error=%s", str(exc))
        raise
