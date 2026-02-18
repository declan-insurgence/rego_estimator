from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Vic Rego Estimator"
    fee_snapshot_blob_container: str = "fee-snapshots"
    fee_snapshot_blob_name: str = "vic/latest.json"
    azure_blob_connection_string: str | None = None
    refresh_frequency_days: int = 30


settings = Settings()
