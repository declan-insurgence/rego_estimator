from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from vic_rego_estimator.auth import AuthError, OIDCAuthenticator
from vic_rego_estimator.tools.registry import TOOLS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vic_rego_estimator")

app = FastAPI(title="Vic Rego Estimator MCP")
authenticator = OIDCAuthenticator.from_settings()

WIDGET_DIR = Path(__file__).parent / "static" / "widget"
app.mount("/widget", StaticFiles(directory=WIDGET_DIR, html=True), name="widget")


@app.middleware("http")
async def redact_logs(request: Request, call_next):
    logger.info("Request %s %s", request.method, request.url.path)
    return await call_next(request)


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


@app.get("/")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "vic-rego-estimator"}


@app.post("/mcp")
async def mcp_endpoint(payload: dict[str, Any]):
    method = payload.get("method")
    req_id = payload.get("id")

    if method == "tools/list":
        tools = [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
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

    raise HTTPException(status_code=400, detail=f"Unsupported MCP method: {method}")


@app.get("/widget-index")
async def widget_index():
    index_file = WIDGET_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Widget not built")
    return FileResponse(index_file)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("vic_rego_estimator.main:app", host="0.0.0.0", port=8080, reload=False)
