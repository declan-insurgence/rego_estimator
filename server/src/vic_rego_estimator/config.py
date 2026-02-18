from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Vic Rego Estimator"
    fee_snapshot_blob_container: str = "fee-snapshots"
    fee_snapshot_blob_name: str = "vic/latest.json"
    azure_blob_connection_string: str | None = None
    refresh_frequency_days: int = 30
    auth_enabled: bool = False
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_client_id: str | None = None
    oidc_jwks_url: str | None = None
    oidc_authorization_url: str | None = None
    oidc_required_scope: str | None = None
    oidc_algorithms: list[str] = ["RS256"]
    mcp_rate_limit_requests: int = 60
    mcp_rate_limit_window_seconds: int = 60


settings = Settings()
