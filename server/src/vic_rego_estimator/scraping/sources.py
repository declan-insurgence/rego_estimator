from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceConfig:
    name: str
    url: str


VIC_SOURCES = [
    SourceConfig("VicRoads light vehicle fees", "https://www.vicroads.vic.gov.au/registration/fees-and-payments"),
    SourceConfig("VicRoads heavy vehicle fees", "https://www.vicroads.vic.gov.au/registration/registration-fees/heavy-vehicle-fees"),
    SourceConfig("VicRoads transfer and duty guidance", "https://www.vicroads.vic.gov.au/registration/fees-and-payments/transfer-fees"),
    SourceConfig("SRO motor vehicle duty rates", "https://www.sro.vic.gov.au/motor-vehicle-duty"),
]
