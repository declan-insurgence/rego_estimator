from __future__ import annotations

import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from vic_rego_estimator.auth import AuthError, OIDCAuthenticator
from vic_rego_estimator.config import settings
from vic_rego_estimator.tools.registry import TOOLS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vic_rego_estimator")

app = FastAPI(title="Vic Rego Estimator MCP")
authenticator = OIDCAuthenticator.from_settings()

WIDGET_DIR = Path(__file__).parent / "static" / "widget"
app.mount("/widget", StaticFiles(directory=WIDGET_DIR, html=True), name="widget")


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int | None = None


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, now: float | None = None) -> RateLimitDecision:
        current_time = now if now is not None else time.time()
        window_start = current_time - self.window_seconds
        bucket = self._requests[key]

        while bucket and bucket[0] <= window_start:
            bucket.popleft()

        if len(bucket) >= self.max_requests:
            retry_after = max(1, int(bucket[0] + self.window_seconds - current_time))
            return RateLimitDecision(allowed=False, retry_after_seconds=retry_after)

        bucket.append(current_time)
        return RateLimitDecision(allowed=True)


rate_limiter = SlidingWindowRateLimiter(
    max_requests=settings.mcp_rate_limit_requests,
    window_seconds=settings.mcp_rate_limit_window_seconds,
)


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _request_identity(request: Request) -> str:
    token_claims = getattr(request.state, "token_claims", None)
    if isinstance(token_claims, dict) and token_claims.get("sub"):
        return f"sub:{token_claims['sub']}"
    return f"ip:{_client_ip(request)}"


@app.middleware("http")
async def request_audit_log(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = request_id
    started_at = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    latency_ms = round((time.perf_counter() - started_at) * 1000, 2)

    log_payload = {
        "event": "http_request",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "latency_ms": latency_ms,
        "client_ip": _client_ip(request),
        "user_agent": request.headers.get("user-agent", "unknown"),
        "authenticated_sub": (
            getattr(request.state, "token_claims", {}).get("sub")
            if isinstance(getattr(request.state, "token_claims", None), dict)
            else None
        ),
    }

    logger.info(json.dumps(log_payload, sort_keys=True))
    return response


@app.middleware("http")
async def enforce_mcp_auth(request: Request, call_next):
    if request.url.path != "/mcp" or authenticator is None:
        return await call_next(request)

    try:
        claims = authenticator.validate_authorization_header(request.headers.get("authorization"))
        request.state.token_claims = claims
    except AuthError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
            headers={
                "WWW-Authenticate": authenticator.challenge_header(
                    error=exc.error,
                    description=exc.message,
                )
            },
        )

    return await call_next(request)


@app.middleware("http")
async def enforce_mcp_rate_limit(request: Request, call_next):
    if request.url.path != "/mcp":
        return await call_next(request)

    identity = _request_identity(request)
    decision = rate_limiter.check(identity)
    if not decision.allowed:
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit exceeded for /mcp",
                "retry_after_seconds": decision.retry_after_seconds,
            },
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )

    return await call_next(request)


@app.get("/")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "vic-rego-estimator"}


@app.post("/mcp")
async def mcp_endpoint(payload: dict[str, Any], request: Request):
    method = payload.get("method")
    req_id = payload.get("id")

    if method == "initialize":
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "vic-rego-estimator",
                        "title": "Vic Rego Estimator MCP",
                        "version": "0.1.0",
                    },
                    "capabilities": {
                        "tools": {
                            "listChanged": False,
                        }
                    },
                    "securitySchemes": _server_security_schemes(),
                },
            }
        )

    if method == "tools/list":
        tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
                "annotations": tool.annotations,
                "securitySchemes": tool.security_schemes,
            }
            for tool in TOOLS.values()
        ]
        return JSONResponse({"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}})

    if method == "tools/call":
        params = payload.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        if tool_name not in TOOLS:
            raise HTTPException(status_code=404, detail=f"Unknown tool {tool_name}")
        envelope = await TOOLS[tool_name].handler(arguments)
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": envelope.content}],
                    "structuredContent": envelope.structuredContent,
                    "meta": envelope.meta,
                },
            }
        )

    logger.warning(
        json.dumps(
            {
                "event": "mcp_unsupported_method",
                "request_id": getattr(request.state, "request_id", None),
                "mcp_method": method,
                "jsonrpc_id": req_id,
            },
            sort_keys=True,
        )
    )
    raise HTTPException(status_code=400, detail=f"Unsupported MCP method: {method}")


def _server_security_schemes() -> list[dict[str, Any]]:
    if authenticator is None:
        return [{"type": "noauth"}]
    return [
        {
            "type": "oauth2",
            "description": "Bearer token required for calling protected MCP methods.",
        }
    ]


@app.get("/widget-index")
async def widget_index():
    index_file = WIDGET_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Widget not built")
    return FileResponse(index_file)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("vic_rego_estimator.main:app", host="0.0.0.0", port=8080, reload=False)
