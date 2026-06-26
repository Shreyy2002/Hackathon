from typing import Dict, Set
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect


class WebSocketManager:
    """
    In-process WebSocket connection registry.
    State: connections = Dict[str, Set[WebSocket]]

    At hackathon scale (3 users) an in-memory dict is sufficient.
    """

    def __init__(self):
        self.connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        if channel not in self.connections:
            self.connections[channel] = set()
        self.connections[channel].add(websocket)

    def disconnect(self, channel: str, websocket: WebSocket) -> None:
        if channel in self.connections:
            self.connections[channel].discard(websocket)
            if not self.connections[channel]:
                del self.connections[channel]

    async def broadcast(self, channel: str, message: dict) -> None:
        """
        Broadcast message to all subscribers for channel.
        Silently removes dead connections.
        """
        if channel not in self.connections:
            return  # no subscribers — silently skip

        dead: list = []
        for ws in list(self.connections[channel]):
            try:
                await ws.send_json(message)
            except (WebSocketDisconnect, RuntimeError):
                dead.append(ws)

        for ws in dead:
            self.disconnect(channel, ws)


# Singleton instance used across the app
websocket_manager = WebSocketManager()
