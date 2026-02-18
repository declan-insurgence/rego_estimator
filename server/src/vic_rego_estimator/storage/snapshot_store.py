from __future__ import annotations

import json
from datetime import datetime, timezone

from azure.storage.blob import BlobServiceClient

from vic_rego_estimator.config import settings
from vic_rego_estimator.models.schemas import FeeSnapshot


class SnapshotStore:
    def __init__(self) -> None:
        self._conn = settings.azure_blob_connection_string

    def _blob_client(self):
        if not self._conn:
            return None
        svc = BlobServiceClient.from_connection_string(self._conn)
        return svc.get_blob_client(
            container=settings.fee_snapshot_blob_container,
            blob=settings.fee_snapshot_blob_name,
        )

    def load(self) -> FeeSnapshot | None:
        client = self._blob_client()
        if client is None:
            return None
        try:
            data = client.download_blob().readall()
            return FeeSnapshot.model_validate_json(data)
        except Exception:
            return None

    def save(self, snapshot: FeeSnapshot) -> None:
        client = self._blob_client()
        if client is None:
            return
        payload = json.dumps(snapshot.model_dump(mode="json")).encode("utf-8")
        client.upload_blob(payload, overwrite=True)


def fallback_snapshot() -> FeeSnapshot:
    return FeeSnapshot(
        refreshed_at=datetime.now(timezone.utc),
        sources=["https://www.vicroads.vic.gov.au/", "https://www.sro.vic.gov.au/motor-vehicle-duty"],
        light_vehicle_fee={"3": 251.10, "6": 493.22, "12": 930.0},
        tac_charge_by_term={"3": 132.50, "6": 265.0, "12": 530.0},
        transfer_fee=46.7,
        number_plate_fee=41.2,
        heavy_vehicle_base_fee={"heavy_vehicle_truck": 1510.0, "bus": 1200.0, "trailer": 430.0, "caravan": 320.0},
        duty_rates=[
            {"threshold": 0, "rate": 0.042},
            {"threshold": 69000, "rate": 0.048},
            {"threshold": 100000, "rate": 0.052},
        ],
        concession_rules={"pensioner": 0.5, "veteran": 0.6, "primary_producer": 0.7},
    )
