"""
WebSocket端点
提供实时事件推送功能
"""
import asyncio
import json
from typing import Set, Dict, Any
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ..dependencies import get_event_manager
from ..services.event_adapter import get_event_adapter
from core.services.interfaces import IEventManager

router = APIRouter(tags=["websocket"])

class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.subscriptions: Dict[WebSocket, Set[str]] = {}
    
    async def connect(self, websocket: WebSocket):
        """接受新的WebSocket连接"""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.subscriptions[websocket] = set()
    
    def disconnect(self, websocket: WebSocket):
        """断开WebSocket连接"""
        self.active_connections.discard(websocket)
        self.subscriptions.pop(websocket, None)
    
    def subscribe(self, websocket: WebSocket, event_types: list):
        """订阅事件类型"""
        if websocket in self.subscriptions:
            self.subscriptions[websocket].update(event_types)
    
    def unsubscribe(self, websocket: WebSocket, event_types: list):
        """取消订阅事件类型"""
        if websocket in self.subscriptions:
            self.subscriptions[websocket].difference_update(event_types)
    
    async def broadcast(self, event_type: str, data: Any):
        """广播事件到所有订阅的客户端"""
        message = json.dumps({
            "type": event_type,
            "data": data
        })
        
        disconnected = []
        for connection in self.active_connections:
            try:
                if event_type in self.subscriptions.get(connection, set()):
                    await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """发送个人消息"""
        try:
            await websocket.send_text(message)
        except Exception:
            self.disconnect(websocket)


manager = ConnectionManager()

def setup_event_handlers(event_manager: IEventManager):
    """设置事件处理器"""
    adapter = get_event_adapter(event_manager)
    
    async def broadcast_handler(data):
        await manager.broadcast("scheduling.started", data)
    
    adapter.register_handler("scheduling.started", broadcast_handler)
    adapter.register_handler("scheduling.progress", 
        lambda d: asyncio.create_task(manager.broadcast("scheduling.progress", d)))
    adapter.register_handler("scheduling.completed", 
        lambda d: asyncio.create_task(manager.broadcast("scheduling.completed", d)))
    adapter.register_handler("scheduling.failed", 
        lambda d: asyncio.create_task(manager.broadcast("scheduling.failed", d)))
    adapter.register_handler("config.updated", 
        lambda d: asyncio.create_task(manager.broadcast("config.updated", d)))
    adapter.register_handler("courses.loaded", 
        lambda d: asyncio.create_task(manager.broadcast("courses.loaded", d)))


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    event_manager: IEventManager = Depends(get_event_manager)
):
    """WebSocket端点"""
    await manager.connect(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                action = message.get("action")
                
                if action == "subscribe":
                    event_types = message.get("event_types", [])
                    manager.subscribe(websocket, event_types)
                    await manager.send_personal_message(
                        json.dumps({"type": "subscribed", "event_types": event_types}),
                        websocket
                    )
                
                elif action == "unsubscribe":
                    event_types = message.get("event_types", [])
                    manager.unsubscribe(websocket, event_types)
                    await manager.send_personal_message(
                        json.dumps({"type": "unsubscribed", "event_types": event_types}),
                        websocket
                    )
                
                elif action == "ping":
                    await manager.send_personal_message(
                        json.dumps({"type": "pong"}),
                        websocket
                    )
                
            except json.JSONDecodeError:
                await manager.send_personal_message(
                    json.dumps({"type": "error", "message": "Invalid JSON"}),
                    websocket
                )
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
