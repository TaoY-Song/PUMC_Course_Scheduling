"""FastAPI application entry point for the web backend."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from contextlib import asynccontextmanager

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
from .services.event_adapter import get_event_adapter

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期（取代已弃用的 @app.on_event("startup")）。"""
    event_manager = get_event_manager()
    setup_event_handlers(event_manager)
    # 🔧 P1 修复：在事件循环线程内绑定 loop，
    # 以便排课工作线程发出的事件能被线程安全地转发到 WebSocket。
    adapter = get_event_adapter(event_manager)
    if adapter is not None:
        adapter.bind_loop(asyncio.get_running_loop())
    yield


app = FastAPI(
    title="PUMC 智能排课系统 - Web API",
    description="PUMC 课程排课系统的 Web API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
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


# settings.static_dir 默认已是绝对路径，但仍允许通过 PUMC_STATIC_DIR
# 传入相对路径；统一 resolve() 使其不受当前工作目录影响。
static_path = Path(settings.static_dir).resolve()

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
