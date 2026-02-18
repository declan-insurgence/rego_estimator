from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from vic_rego_estimator.tools.registry import TOOLS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("vic_rego_estimator")

app = FastAPI(title="Vic Rego Estimator MCP")

WIDGET_DIR = Path(__file__).parent / "static" / "widget"
app.mount("/widget", StaticFiles(directory=WIDGET_DIR, html=True), name="widget")


@app.middleware("http")
async def redact_logs(request: Request, call_next):
    logger.info("request_started method=%s path=%s", request.method, request.url.path)
    try:
        response = await call_next(request)
        logger.info(
            "request_finished method=%s path=%s status_code=%s",
            request.method,
            request.url.path,
            response.status_code,
        )
        return response
    except Exception as exc:
        logger.exception(
            "request_failed method=%s path=%s error=%s",
            request.method,
            request.url.path,
            str(exc),
        )
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "vic-rego-estimator"}


@app.post("/mcp")
async def mcp_endpoint(payload: dict[str, Any]):
    method = payload.get("method")
    req_id = payload.get("id")

    try:
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
            if not isinstance(arguments, dict):
                raise HTTPException(status_code=400, detail="Tool arguments must be an object")
            if tool_name not in TOOLS:
                raise HTTPException(status_code=404, detail=f"Unknown tool {tool_name}")

            logger.info("tool_call name=%s", tool_name)
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
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("mcp_endpoint_failed method=%s error=%s", method, str(exc))
        raise HTTPException(status_code=500, detail="Failed to process MCP request") from exc


@app.get("/widget-index")
async def widget_index():
    index_file = WIDGET_DIR / "index.html"
    if not index_file.exists():
        logger.warning("widget_index_missing path=%s", index_file)
        raise HTTPException(status_code=404, detail="Widget not built")
    return FileResponse(index_file)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("vic_rego_estimator.main:app", host="0.0.0.0", port=8080, reload=False)
