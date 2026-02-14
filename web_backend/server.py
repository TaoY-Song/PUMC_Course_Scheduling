"""
FastAPI应用入口
提供Web后端API服务和静态文件服务
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import settings
from .api import courses, scheduling, export, websocket
from .dependencies import get_event_manager
from .api.websocket import setup_event_handlers

app = FastAPI(
    title="PUMC智能排课系统 - Web API",
    description="PUMC课程排课系统的Web版本API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
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
app.include_router(websocket.router)


@app.on_event("startup")
async def startup_event():
    from web_backend.dependencies import get_event_manager
    event_manager_gen = get_event_manager()
    event_manager = next(event_manager_gen)
    setup_event_handlers(event_manager)


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
    return {
        "message": "PUMC智能排课系统Web API",
        "docs": "/docs",
        "version": "1.0.0"
    }

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
