"""
JARVIS Error Handler Middleware
===============================
Structured error responses with logging and correlation IDs.
"""

import os
import time
import uuid
import traceback
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Global error handler that returns structured JSON errors."""

    async def dispatch(self, request: Request, call_next):
        correlation_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # WebSocket upgrade requests must not be intercepted by BaseHTTPMiddleware
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        try:
            response = await call_next(request)
            return response
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "error": e.detail,
                    "status_code": e.status_code,
                    "correlation_id": correlation_id,
                    "path": request.url.path,
                },
            )
        except Exception as e:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            error_detail = str(e) if os.getenv("JARVIS_DEBUG") else "Internal server error"

            # Log the full traceback in production logs
            tb = traceback.format_exc()
            print(f"[ERROR] {correlation_id} {request.method} {request.url.path} "
                  f"({duration_ms}ms): {type(e).__name__}: {e}")
            if os.getenv("JARVIS_DEBUG"):
                print(f"[ERROR] {correlation_id} Traceback:\n{tb}")

            return JSONResponse(
                status_code=500,
                content={
                    "error": error_detail,
                    "error_type": type(e).__name__,
                    "status_code": 500,
                    "correlation_id": correlation_id,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
                headers={"X-Correlation-ID": correlation_id},
            )
