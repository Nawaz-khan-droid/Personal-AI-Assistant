"""
WebSocket connection manager for handling multiple concurrent connections.

Why: WebSocket connections need careful lifecycle management - we need to:
- Track active connections
- Handle reconnection
- Broadcast messages to specific sessions
- Clean up gracefully on disconnect

Best Practice: Centralize WebSocket logic rather than scattering it across endpoints.
Error Prevention: Using asyncio.Queue prevents race conditions when sending messages.
"""

import asyncio
import logging
from typing import Dict, Optional
from fastapi import WebSocket
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages WebSocket connections and message distribution.
    """
    
    def __init__(self):
        # Active connections: {session_id: websocket}
        self.active_connections: Dict[str, WebSocket] = {}
        # Message queues for each connection
        self.message_queues: Dict[str, asyncio.Queue] = {}
        # Connection metadata
        self.connection_info: Dict[str, Dict] = {}
        
        logger.info("WebSocket manager initialized")
    
    async def connect(self, websocket: WebSocket) -> str:
        session_id = str(uuid.uuid4())
        self.active_connections[session_id] = websocket
        self.message_queues[session_id] = asyncio.Queue()
        self.connection_info[session_id] = {
            "connected_at": datetime.utcnow(),
            "messages_sent": 0,
            "messages_received": 0
        }
        
        logger.info(
            "WebSocket connected",
            extra={
                "session_id": session_id,
                "total_connections": len(self.active_connections)
            }
        )
        return session_id
    
    async def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        
        if session_id in self.message_queues:
            del self.message_queues[session_id]
        
        if session_id in self.connection_info:
            info = self.connection_info[session_id]
            duration = (datetime.utcnow() - info["connected_at"]).total_seconds()
            logger.info(
                "WebSocket disconnected",
                extra={
                    "session_id": session_id,
                    "duration_seconds": duration,
                    "messages_sent": info["messages_sent"],
                    "messages_received": info["messages_received"]
                }
            )
            del self.connection_info[session_id]
    
    async def send_message(self, session_id: str, message: dict):
        if session_id not in self.active_connections:
            return
        
        try:
            websocket = self.active_connections[session_id]
            await websocket.send_json(message)
            if session_id in self.connection_info:
                self.connection_info[session_id]["messages_sent"] += 1
        except RuntimeError as e:
            logger.debug(f"WebSocket closed during JSON send: {e}", extra={"session_id": session_id})
            await self.disconnect(session_id)
            raise e
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}", extra={"session_id": session_id})
            raise e
    
    async def broadcast(self, message: dict, exclude: Optional[str] = None):
        for session_id in list(self.active_connections.keys()):
            if session_id != exclude:
                try:
                    await self.send_message(session_id, message)
                except Exception:
                    pass
    
    async def send_text(self, session_id: str, text: str):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_text(text)
            except RuntimeError as e:
                logger.debug(f"WebSocket closed during text send: {e}", extra={"session_id": session_id})
                await self.disconnect(session_id)
                raise e
            except Exception as e:
                logger.error(f"Failed to send text: {e}")
                raise e
    
    async def send_bytes(self, session_id: str, data: bytes):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_bytes(data)
            except RuntimeError as e:
                logger.debug(f"WebSocket closed during bytes send: {e}", extra={"session_id": session_id})
                await self.disconnect(session_id)
                raise e
            except Exception as e:
                logger.error(f"Failed to send bytes: {e}")
                raise e
    
    def get_active_count(self) -> int:
        return len(self.active_connections)
    
    async def keepalive(self, session_id: str, interval: int = 30):
        while session_id in self.active_connections:
            try:
                await self.send_message(session_id, {"type": "ping"})
                await asyncio.sleep(interval)
            except Exception:
                await self.disconnect(session_id)
                break

# Global instance - shared across all endpoints
manager = ConnectionManager()

