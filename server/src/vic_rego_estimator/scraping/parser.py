from __future__ import annotations

import io
import re
from datetime import datetime, timezone
from typing import Any

import httpx
import pdfplumber
from bs4 import BeautifulSoup

from vic_rego_estimator.models.schemas import FeeSnapshot
from vic_rego_estimator.scraping.sources import VIC_SOURCES

CURRENCY_RE = re.compile(r"\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)")


def _extract_first_currency(text: str, fallback: float) -> float:
    match = CURRENCY_RE.search(text)
    if not match:
        return fallback
    return float(match.group(1).replace(",", ""))


def _parse_html_tables(html: str) -> dict[str, float]:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    return {
        "registration_fee_12": _extract_first_currency(text, 930.0),
        "tac_12": _extract_first_currency(text[text.find("TAC") :], 530.0),
        "transfer_fee": _extract_first_currency(text[text.find("transfer") :], 46.7),
        "number_plate_fee": _extract_first_currency(text[text.find("plate") :], 41.2),
    }


def _parse_pdf_table(pdf_bytes: bytes) -> dict[str, float]:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        all_text = " ".join((page.extract_text() or "") for page in pdf.pages)
    return {
        "heavy_truck_base": _extract_first_currency(all_text, 1510.0),
        "bus_base": _extract_first_currency(all_text[all_text.find("bus") :], 1200.0),
    }


async def scrape_fee_snapshot() -> FeeSnapshot:
    parsed: dict[str, Any] = {}
    urls = [source.url for source in VIC_SOURCES]
    async with httpx.AsyncClient(timeout=20) as client:
        for source in VIC_SOURCES:
            response = await client.get(source.url)
            response.raise_for_status()
            if ".pdf" in source.url:
                parsed.update(_parse_pdf_table(response.content))
            else:
                parsed.update(_parse_html_tables(response.text))

    reg12 = parsed.get("registration_fee_12", 930.0)
    tac12 = parsed.get("tac_12", 530.0)

    return FeeSnapshot(
        refreshed_at=datetime.now(timezone.utc),
        sources=urls,
        light_vehicle_fee={"3": round(reg12 * 0.27, 2), "6": round(reg12 * 0.53, 2), "12": reg12},
        tac_charge_by_term={"3": round(tac12 * 0.25, 2), "6": round(tac12 * 0.5, 2), "12": tac12},
        transfer_fee=parsed.get("transfer_fee", 46.7),
        number_plate_fee=parsed.get("number_plate_fee", 41.2),
        heavy_vehicle_base_fee={
            "heavy_vehicle_truck": parsed.get("heavy_truck_base", 1510.0),
            "bus": parsed.get("bus_base", 1200.0),
            "trailer": 430.0,
            "caravan": 320.0,
        },
        duty_rates=[
            {"threshold": 0, "rate": 0.042},
            {"threshold": 69000, "rate": 0.048},
            {"threshold": 100000, "rate": 0.052},
        ],
        concession_rules={"pensioner": 0.5, "veteran": 0.6, "primary_producer": 0.7},
    )
