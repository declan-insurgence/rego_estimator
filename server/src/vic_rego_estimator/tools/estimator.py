from __future__ import annotations

import logging

from vic_rego_estimator.models.schemas import EstimateResult, FeeLineItem, FeeSnapshot, NormalizedVehicleRequest

logger = logging.getLogger("vic_rego_estimator.estimator")


def _duty_amount(value: float, rates: list[dict[str, float]]) -> float:
    rate = rates[0]["rate"]
    for band in rates:
        if value >= band["threshold"]:
            rate = band["rate"]
    return round(value * rate, 2)


def estimate_registration_cost(normalized: NormalizedVehicleRequest, snapshot: FeeSnapshot) -> EstimateResult:
    try:
        term_key = str(normalized.term_months)
        lines: list[FeeLineItem] = []
        assumptions = list(normalized.assumptions)
        concessions_applied: list[str] = []

        if normalized.vehicle_category in {"heavy_vehicle_truck", "bus", "trailer", "caravan"}:
            reg_fee = snapshot.heavy_vehicle_base_fee.get(normalized.vehicle_category, 930.0)
            reg_fee *= normalized.term_months / 12
        else:
            reg_fee = snapshot.light_vehicle_fee[term_key]

        tac = snapshot.tac_charge_by_term[term_key]

        reg_discount = 1.0
        for flag, enabled in normalized.concession_flags.items():
            if enabled and flag in snapshot.concession_rules:
                reg_discount = min(reg_discount, snapshot.concession_rules[flag])
                concessions_applied.append(flag)

        reg_fee *= reg_discount

        lines.append(FeeLineItem(key="registration_fee", label="Registration fee", amount_min=round(reg_fee, 2), amount_max=round(reg_fee, 2), source=snapshot.sources[0]))
        lines.append(FeeLineItem(key="tac_charge", label="TAC charge", amount_min=round(tac, 2), amount_max=round(tac, 2), source=snapshot.sources[0]))

        if normalized.transaction_type == "transfer":
            lines.append(FeeLineItem(key="transfer_fee", label="Transfer fee", amount_min=snapshot.transfer_fee, amount_max=snapshot.transfer_fee, source=snapshot.sources[2]))
            if normalized.market_value_aud is None:
                duty_min = _duty_amount(10000, snapshot.duty_rates)
                duty_max = _duty_amount(45000, snapshot.duty_rates)
                assumptions.append("Used $10k-$45k market value range for duty.")
            else:
                duty_min = duty_max = _duty_amount(normalized.market_value_aud, snapshot.duty_rates)
            lines.append(FeeLineItem(key="motor_vehicle_duty", label="Motor vehicle duty (stamp duty)", amount_min=duty_min, amount_max=duty_max, source=snapshot.sources[3]))

        if normalized.transaction_type == "new_registration":
            lines.append(FeeLineItem(key="number_plate_fee", label="Number plate fee", amount_min=snapshot.number_plate_fee, amount_max=snapshot.number_plate_fee, source=snapshot.sources[0]))

        if normalized.use_type == "business":
            admin_fee = 18.4
            lines.append(FeeLineItem(key="business_admin", label="Business processing surcharge", amount_min=admin_fee, amount_max=admin_fee, source=snapshot.sources[0], notes="May vary by channel."))

        for key, value in normalized.manual_overrides.items():
            for line in lines:
                if line.key == key:
                    line.amount_min = value
                    line.amount_max = value
                    line.notes = "Manually overridden in widget"

        total_min = round(sum(item.amount_min for item in lines), 2)
        total_max = round(sum(item.amount_max for item in lines), 2)

        uncertainty_points = len(normalized.unknown_fields) + (1 if total_min != total_max else 0)
        confidence = "high" if uncertainty_points == 0 else "medium" if uncertainty_points <= 2 else "low"
        score = max(0.3, round(1 - uncertainty_points * 0.15, 2))

        return EstimateResult(
            transaction_type=normalized.transaction_type,
            vehicle_category=normalized.vehicle_category,
            total_min=total_min,
            total_max=total_max,
            confidence=confidence,
            confidence_score=score,
            line_items=lines,
            assumptions=assumptions,
            concessions_applied=concessions_applied,
            last_refresh=snapshot.refreshed_at,
            source_urls=snapshot.sources,
        )
    except KeyError as exc:
        logger.exception("estimate_key_error term_or_source_missing error=%s", str(exc))
        raise ValueError("Snapshot is missing required fee keys") from exc
    except Exception as exc:
        logger.exception("estimate_unexpected_error error=%s", str(exc))
        raise
