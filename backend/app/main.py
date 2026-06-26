from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect
from app.services.websocket_manager import websocket_manager

app = FastAPI(title="Event-Sourced Performance Ledger", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers included now (auth + employees + timeline + goals)
from app.routers import auth, employees, timeline, goals
app.include_router(auth.router, prefix="/api")
app.include_router(employees.router, prefix="/api")
app.include_router(timeline.router, prefix="/api")
app.include_router(goals.router, prefix="/api")
# TODO task 3.3: app.include_router(reviews.router, prefix="/api")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.websocket("/ws/{employee_id}")
async def websocket_endpoint(websocket: WebSocket, employee_id: str):
    await websocket_manager.connect(employee_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # keep connection alive
    except WebSocketDisconnect:
        websocket_manager.disconnect(employee_id, websocket)
