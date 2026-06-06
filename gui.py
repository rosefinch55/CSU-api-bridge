import asyncio
import subprocess
import os
import json
from pathlib import Path

import aiohttp
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from dotenv import dotenv_values
import uvicorn

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
PROVIDERS_PATH = BASE_DIR / "providers.json"

app = FastAPI(title="API Bridge GUI")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# 内置厂商（初始默认）
DEFAULT_PROVIDERS = {
    "csu": {
        "name": "CSU 大学云",
        "description": "通过本地 Bridge 代理连接",
        "requires_bridge": True,
        "url": "https://api.chat.csu.edu.cn/v1",
        "key": "",
        "models_endpoint": "/models",
        "models": [
            {"id": "csu-deepseek", "label": "DeepSeek"},
            {"id": "csu-deepseek-thinking", "label": "DeepSeek Thinking"},
            {"id": "csu-qwen", "label": "Qwen"},
        ],
    },
    "mimo": {
        "name": "小米 Mimo",
        "description": "直连小米 API",
        "requires_bridge": False,
        "url": "https://token-plan-cn.xiaomimimo.com/anthropic",
        "key": "",
        "models_endpoint": "",
        "models": [
            {"id": "mimo-v2.5-pro", "label": "Mimo v2.5 Pro"},
            {"id": "mimo-v2.5", "label": "Mimo v2.5"},
        ],
    },
}

# 运行状态
bridge_process = None
claude_process = None


class LogBroadcaster:
    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self):
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def publish(self, message: str):
        for q in list(self._subscribers):
            await q.put(message)


log_broadcaster = LogBroadcaster()


# ── 厂商配置持久化 ──────────────────────────────────────────────

def load_providers() -> dict:
    if PROVIDERS_PATH.exists():
        try:
            return json.loads(PROVIDERS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return DEFAULT_PROVIDERS.copy()


def save_providers(providers: dict):
    PROVIDERS_PATH.write_text(json.dumps(providers, ensure_ascii=False, indent=2), encoding="utf-8")


def read_env() -> dict[str, str]:
    return dotenv_values(ENV_PATH)


def write_env(values: dict[str, str]):
    current = read_env()
    current.update(values)
    lines = [f"{k}={current[k]}" for k in current]
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── 页面路由 ────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    env = read_env()
    providers = load_providers()
    selected_provider = env.get("GUI_SELECTED_PROVIDER", "csu")
    selected_model = env.get("GUI_SELECTED_MODEL", "")

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "providers": providers,
            "selected_provider": selected_provider,
            "selected_model": selected_model,
            "env": env,
        },
    )


@app.post("/save")
async def save(request: Request):
    form = await request.form()
    provider_id = form.get("provider", "csu")

    data = {
        "GUI_SELECTED_PROVIDER": provider_id,
        "GUI_SELECTED_MODEL": str(form.get("model", "")),
    }

    # 保存厂商配置
    providers = load_providers()
    if provider_id in providers:
        providers[provider_id]["url"] = str(form.get("url", ""))
        providers[provider_id]["key"] = str(form.get("key", ""))
        save_providers(providers)

    # 也写 env（兼容旧逻辑）
    data["CSU_URL"] = str(form.get("url", "")) if provider_id == "csu" else read_env().get("CSU_URL", "")
    data["CSU_KEY"] = str(form.get("key", "")) if provider_id == "csu" else read_env().get("CSU_KEY", "")
    data["MIMO_URL"] = str(form.get("url", "")) if provider_id in ("mimo", "xiaomi") else read_env().get("MIMO_URL", "")
    data["MIMO_KEY"] = str(form.get("key", "")) if provider_id in ("mimo", "xiaomi") else read_env().get("MIMO_KEY", "")

    write_env(data)
    return RedirectResponse("/", status_code=303)


# ── 厂商 CRUD ──────────────────────────────────────────────────

@app.post("/api/provider/create")
async def create_provider(request: Request):
    form = await request.form()
    provider_id = form.get("id", "").strip().lower().replace(" ", "-")
    if not provider_id:
        return JSONResponse({"error": "ID 不能为空"}, status_code=400)

    providers = load_providers()
    if provider_id in providers:
        return JSONResponse({"error": "厂商 ID 已存在"}, status_code=400)

    providers[provider_id] = {
        "name": form.get("name", provider_id),
        "description": form.get("description", ""),
        "requires_bridge": form.get("requires_bridge", "false") == "true",
        "url": form.get("url", ""),
        "key": form.get("key", ""),
        "models_endpoint": form.get("models_endpoint", ""),
        "models": [],
    }
    save_providers(providers)
    return JSONResponse({"status": "ok", "id": provider_id})


@app.post("/api/provider/update")
async def update_provider(request: Request):
    form = await request.form()
    provider_id = form.get("id", "")
    providers = load_providers()

    if provider_id not in providers:
        return JSONResponse({"error": "厂商不存在"}, status_code=404)

    p = providers[provider_id]
    p["name"] = form.get("name", p["name"])
    p["description"] = form.get("description", p["description"])
    p["url"] = form.get("url", p["url"])
    p["key"] = form.get("key", p["key"])
    p["models_endpoint"] = form.get("models_endpoint", p.get("models_endpoint", ""))
    save_providers(providers)
    return JSONResponse({"status": "ok"})


@app.post("/api/provider/delete")
async def delete_provider(request: Request):
    form = await request.form()
    provider_id = form.get("id", "")
    providers = load_providers()

    if provider_id not in providers:
        return JSONResponse({"error": "厂商不存在"}, status_code=404)

    del providers[provider_id]
    save_providers(providers)
    return JSONResponse({"status": "ok"})


# ── 模型拉取 ───────────────────────────────────────────────────

@app.post("/api/models/fetch")
async def fetch_models(request: Request):
    form = await request.form()
    provider_id = form.get("provider", "")
    providers = load_providers()

    if provider_id not in providers:
        return JSONResponse({"error": "厂商不存在"}, status_code=404)

    p = providers[provider_id]
    url = p.get("url", "").rstrip("/")
    key = p.get("key", "")
    endpoint = p.get("models_endpoint", "/models")

    if not url:
        return JSONResponse({"error": "请先配置 URL"}, status_code=400)

    # 尝试拉取模型列表
    models_url = url + endpoint
    headers = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    await log_broadcaster.publish(f"[GUI] 正在从 {models_url} 拉取模型...")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(models_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    await log_broadcaster.publish(f"[GUI] 拉取失败: HTTP {resp.status}")
                    return JSONResponse({"error": f"HTTP {resp.status}", "detail": text[:200]}, status_code=400)

                data = await resp.json()
                await log_broadcaster.publish(f"[GUI] 拉取成功，解析中...")

    except Exception as e:
        await log_broadcaster.publish(f"[GUI] 拉取异常: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

    # 解析模型列表（兼容 OpenAI 格式）
    model_list = []
    raw_models = data.get("data", data.get("models", []))

    if isinstance(raw_models, list):
        for m in raw_models:
            if isinstance(m, str):
                model_list.append({"id": m, "label": m})
            elif isinstance(m, dict):
                mid = m.get("id", m.get("name", ""))
                if mid:
                    model_list.append({"id": mid, "label": mid})

    if not model_list:
        await log_broadcaster.publish("[GUI] 未解析到模型，保持原列表")
        return JSONResponse({"models": p.get("models", []), "message": "未解析到模型"})

    # 更新厂商配置
    p["models"] = model_list
    save_providers(providers)

    await log_broadcaster.publish(f"[GUI] 已更新 {len(model_list)} 个模型")
    return JSONResponse({"models": model_list})


# ── 启停控制 ───────────────────────────────────────────────────

@app.post("/api/start")
async def start_bridge(request: Request):
    global bridge_process, claude_process

    form = await request.form()
    provider_id = form.get("provider", "csu")
    providers = load_providers()
    provider = providers.get(provider_id)

    if not provider:
        return JSONResponse({"error": "未知厂商"}, status_code=400)

    env = read_env()
    model = env.get("GUI_SELECTED_MODEL", "")
    if not model and provider.get("models"):
        model = provider["models"][0]["id"]

    # 准备环境变量
    claude_env = os.environ.copy()

    if provider.get("requires_bridge"):
        if bridge_process and bridge_process.poll() is None:
            await log_broadcaster.publish("[GUI] Bridge 已在运行")
        else:
            await log_broadcaster.publish("[GUI] 启动 Bridge 服务...")
            bridge_process = subprocess.Popen(
                ["python", str(BASE_DIR / "server.py")],
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            await asyncio.sleep(2)
            await log_broadcaster.publish("[GUI] Bridge 已启动")

        claude_env["ANTHROPIC_BASE_URL"] = "http://localhost:4000"
    else:
        claude_env["ANTHROPIC_BASE_URL"] = provider.get("url", "")

    claude_env["ANTHROPIC_AUTH_TOKEN"] = provider.get("key", "")
    claude_env["ANTHROPIC_MODEL"] = model

    await log_broadcaster.publish(f"[GUI] 启动 Claude Code (模型: {model})...")

    claude_process = subprocess.Popen(
        ["claude", "--enable-auto-mode"],
        cwd=str(BASE_DIR),
        env=claude_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )

    return JSONResponse({
        "status": "started",
        "provider": provider_id,
        "model": model,
        "pid": claude_process.pid,
    })


@app.post("/api/stop")
async def stop():
    global bridge_process, claude_process
    stopped = []

    if claude_process and claude_process.poll() is None:
        claude_process.terminate()
        stopped.append("Claude")
        await log_broadcaster.publish("[GUI] Claude Code 已停止")

    if bridge_process and bridge_process.poll() is None:
        bridge_process.terminate()
        stopped.append("Bridge")
        await log_broadcaster.publish("[GUI] Bridge 已停止")

    return JSONResponse({"stopped": stopped})


@app.get("/api/status")
async def status():
    return JSONResponse({
        "bridge_running": bridge_process is not None and bridge_process.poll() is None,
        "claude_running": claude_process is not None and claude_process.poll() is None,
    })


@app.websocket("/ws/logs")
async def ws_logs(ws: WebSocket):
    await ws.accept()
    q = log_broadcaster.subscribe()
    try:
        while True:
            message = await q.get()
            await ws.send_text(message)
    except WebSocketDisconnect:
        pass
    finally:
        log_broadcaster.unsubscribe(q)


if __name__ == "__main__":
    port = int(read_env().get("GUI_PORT", "4100"))
    print(f"API Bridge GUI running on http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
