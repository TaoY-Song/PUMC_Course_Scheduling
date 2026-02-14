"""
API路由模块
"""
from .courses import router as courses_router
from .scheduling import router as scheduling_router
from .export import router as export_router
from .websocket import router as websocket_router

__all__ = [
    "courses_router",
    "scheduling_router", 
    "export_router",
    "websocket_router"
]
