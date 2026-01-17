import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import os
import json
import asyncio
from pathlib import Path

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
MODELS_DIR = BASE_DIR / "live2d_models"

# --- 启动自检 ---
print("\n" + "="*40)
print(f"Live2D Server Diagnostic")
print("="*40)

if not WEB_DIR.exists():
    print(f"[ERROR] ❌ 找不到 web 文件夹！\n路径: {WEB_DIR}")
else:
    print(f"[OK] ✅ Web 目录已挂载")

if not MODELS_DIR.exists():
    print(f"[ERROR] ❌ 找不到 live2d_models 文件夹！\n路径: {MODELS_DIR}")
else:
    print(f"[OK] ✅ Models 目录已挂载")
    models = list(MODELS_DIR.rglob("*.model3.json"))
    if not models:
        print("[WARNING] ⚠ 警告: 在 live2d_models 里没找到任何 .model3.json 文件！")
    else:
        print(f"发现 {len(models)} 个可用模型，请确保你的 index.html 里填的是下面这个路径：")
        for m in models:
            rel_path = m.relative_to(BASE_DIR).as_posix()
            print(f"\n   👉 /{rel_path}\n")

print("="*40 + "\n")

if WEB_DIR.exists():
    app.mount("/web", StaticFiles(directory=WEB_DIR, html=True), name="web")
if MODELS_DIR.exists():
    app.mount("/live2d_models", StaticFiles(directory=MODELS_DIR), name="models")

@app.get("/")
async def root():
    return RedirectResponse(url="/web/")

# --- WebSocket 管理 ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WS] 新的前端连接已建立 (当前总数: {len(self.active_connections)})")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"[WS] 前端断开连接 (剩余: {len(self.active_connections)})")

    async def broadcast(self, message: dict):
        # [关键修改] 打印发送的指令，方便调试
        print(f"   >>> [BROADCAST] 发送指令给前端: {message}")
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        manager.disconnect(websocket)

# --- 控制接口 ---
@app.post("/control")
async def control_live2d(data: dict):
    # [关键修改] 收到请求时打印
    print(f"\n[API] 收到控制请求: {data}")
    await manager.broadcast(data)
    return {"status": "sent"}

if __name__ == "__main__":
    print("Live2D Server starting...")
    print("请访问: http://127.0.0.1:8000/web/")
    uvicorn.run(app, host="127.0.0.1", port=8000)