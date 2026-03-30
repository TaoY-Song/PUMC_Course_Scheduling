"""FastAPI application entry point for the web backend."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).parent.parent))


def _configure_console_streams() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(errors="replace")
            except Exception:
                pass


_configure_console_streams()

from .api import courses, export, scheduling, supplement, websocket
from .api.websocket import setup_event_handlers
from .config import settings
from .dependencies import get_event_manager

app = FastAPI(
    title="PUMC 智能排课系统 - Web API",
    description="PUMC 课程排课系统的 Web API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

app.include_router(courses.router, prefix="/api")
app.include_router(scheduling.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(supplement.router, prefix="/api")
app.include_router(websocket.router)


@app.on_event("startup")
async def startup_event():
    setup_event_handlers(get_event_manager())


static_path = Path(settings.static_dir)

if static_path.exists():
    assets_path = static_path / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")


@app.get("/")
async def root():
    index_file = static_path / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "PUMC 智能排课系统 Web API", "docs": "/docs", "version": "1.0.0"}


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404)

    if static_path.exists():
        file_path = static_path / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))

        index_file = static_path / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))

    return {"error": "Not found"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
