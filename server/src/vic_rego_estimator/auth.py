from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from vic_rego_estimator.config import settings

logger = logging.getLogger("vic_rego_estimator")


class AuthError(Exception):
    def __init__(self, message: str, error: str = "invalid_token", status_code: int = 401) -> None:
        self.message = message
        self.error = error
        self.status_code = status_code
        super().__init__(message)


@dataclass(slots=True)
class OIDCAuthenticator:
    issuer: str
    audience: str
    client_id: str
    jwks_url: str
    authorization_url: str
    algorithms: list[str]
    required_scope: str | None

    @classmethod
    def from_settings(cls) -> OIDCAuthenticator | None:
        if not settings.auth_enabled:
            return None

        required_fields = {
            "oidc_issuer": settings.oidc_issuer,
            "oidc_audience": settings.oidc_audience,
            "oidc_client_id": settings.oidc_client_id,
            "oidc_jwks_url": settings.oidc_jwks_url,
        }
        missing = [name for name, value in required_fields.items() if not value]
        if missing:
            raise RuntimeError(
                f"OIDC authentication is enabled but missing required settings: {', '.join(missing)}"
            )

        authorization_url = settings.oidc_authorization_url or f"{settings.oidc_issuer.rstrip('/')}/authorize"
        return cls(
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
            client_id=settings.oidc_client_id,
            jwks_url=settings.oidc_jwks_url,
            authorization_url=authorization_url,
            algorithms=settings.oidc_algorithms,
            required_scope=settings.oidc_required_scope,
        )

    def validate_authorization_header(self, authorization_header: str | None) -> dict[str, Any]:
        if not authorization_header:
            raise AuthError("Missing bearer token", error="invalid_request")

        scheme, _, token = authorization_header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise AuthError("Authorization header must be a bearer token", error="invalid_request")

        return self.validate_token(token)

    def validate_token(self, token: str) -> dict[str, Any]:
        try:
            header, payload, signature, signing_input = _split_jwt(token)
            if header.get("alg") not in self.algorithms:
                raise AuthError(f"Unsupported signing algorithm: {header.get('alg')}")
            if header.get("alg") != "RS256":
                raise AuthError("Only RS256 tokens are supported")
            key = self._resolve_key(header)
            key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
            _validate_registered_claims(payload, issuer=self.issuer, audience=self.audience)
        except AuthError:
            raise
        except Exception as exc:  # pragma: no cover - defensive catch for crypto parsing
            logger.warning("Token validation failed: %s", exc)
            raise AuthError("Token is invalid or expired") from exc

        if self.required_scope and not _has_required_scope(payload, self.required_scope):
            raise AuthError(
                f"Token missing required scope: {self.required_scope}",
                error="insufficient_scope",
                status_code=403,
            )

        return payload

    def _resolve_key(self, header: dict[str, Any]) -> rsa.RSAPublicKey:
        kid = header.get("kid")
        if not kid:
            raise AuthError("Token header missing 'kid'")

        jwks = _fetch_jwks(self.jwks_url)
        for jwk in jwks.get("keys", []):
            if jwk.get("kid") == kid:
                return _jwk_to_rsa_public_key(jwk)
        raise AuthError("Unable to find signing key for token")

    def challenge_header(self, error: str, description: str) -> str:
        parts = [
            'Bearer realm="vic-rego-estimator"',
            f'authorization_uri="{self.authorization_url}"',
            f'resource="{self.audience}"',
            f'client_id="{self.client_id}"',
            f'error="{error}"',
            f'error_description="{description}"',
        ]
        if self.required_scope:
            parts.append(f'scope="{self.required_scope}"')
        return ", ".join(parts)


def _split_jwt(token: str) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthError("Token is malformed")

    header_segment, payload_segment, signature_segment = parts
    header = json.loads(_b64url_decode(header_segment).decode("utf-8"))
    payload = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
    signature = _b64url_decode(signature_segment)
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    return header, payload, signature, signing_input


def _validate_registered_claims(payload: dict[str, Any], issuer: str, audience: str) -> None:
    now = int(time.time())

    exp = payload.get("exp")
    iat = payload.get("iat")
    iss = payload.get("iss")
    aud = payload.get("aud")

    if not isinstance(exp, (int, float)) or now >= int(exp):
        raise AuthError("Token is invalid or expired")
    if not isinstance(iat, (int, float)) or int(iat) > now + 60:
        raise AuthError("Token has invalid issue timestamp")
    if iss != issuer:
        raise AuthError("Token issuer mismatch")

    if isinstance(aud, str):
        audiences = {aud}
    elif isinstance(aud, list):
        audiences = set(aud)
    else:
        audiences = set()

    if audience not in audiences:
        raise AuthError("Token audience mismatch")


def _fetch_jwks(jwks_url: str) -> dict[str, Any]:
    with httpx.Client(timeout=5.0) as client:
        response = client.get(jwks_url)
        response.raise_for_status()
        return response.json()


def _jwk_to_rsa_public_key(jwk: dict[str, Any]) -> rsa.RSAPublicKey:
    if jwk.get("kty") != "RSA":
        raise AuthError("Only RSA JWK keys are supported")

    n = int.from_bytes(_b64url_decode(jwk["n"]), byteorder="big")
    e = int.from_bytes(_b64url_decode(jwk["e"]), byteorder="big")
    numbers = rsa.RSAPublicNumbers(e=e, n=n)
    return numbers.public_key()


def _b64url_decode(value: str) -> bytes:
    padding_length = (-len(value)) % 4
    return base64.urlsafe_b64decode(value + ("=" * padding_length))


def _has_required_scope(claims: dict[str, Any], required_scope: str) -> bool:
    scope_claim = claims.get("scope", "")
    if isinstance(scope_claim, str):
        scopes = set(scope_claim.split())
    else:
        scopes = set()

    scp_claim = claims.get("scp", [])
    if isinstance(scp_claim, str):
        scopes.update(scp_claim.split())
    elif isinstance(scp_claim, list):
        scopes.update(scp_claim)

    return required_scope in scopes
