import os
import json
import uuid
import httpx
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("apibridge")

# Load .env
load_dotenv(Path(__file__).parent / ".env")

app = FastAPI()

# ========== Configuration ==========
ENABLE_THINKING = os.getenv("ENABLE_THINKING", "false").lower() == "true"
BASE_DIR = Path(__file__).resolve().parent
PROVIDERS_PATH = BASE_DIR / "providers.json"


def load_providers() -> dict:
    """从 providers.json 加载厂商配置"""
    if PROVIDERS_PATH.exists():
        try:
            return json.loads(PROVIDERS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def build_upstreams() -> dict:
    """从 providers.json 动态构建 UPSTREAMS"""
    upstreams = {}
    providers = load_providers()

    for provider_id, provider in providers.items():
        url = provider.get("url", "")
        key = provider.get("key", "")
        if not url:
            continue

        # 判断协议类型
        if "anthropic" in url:
            protocol = "anthropic"
        else:
            protocol = "openai"

        upstreams[provider_id] = {
            "url": url,
            "key": key,
            "protocol": protocol,
        }

    return upstreams


# 动态构建 UPSTREAMS
UPSTREAMS = build_upstreams()
PORT = int(os.getenv("PORT", "4000"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "300"))
BIND_HOST = os.getenv("BIND_HOST", "0.0.0.0")


def build_model_map() -> dict:
    """从 providers.json 动态构建 MODEL_MAP"""
    model_map = {}
    providers = load_providers()

    for provider_id, provider in providers.items():
        if provider_id not in UPSTREAMS:
            continue
        for model in provider.get("models", []):
            model_id = model["id"]
            model_map[model_id] = (provider_id, model_id)

    # 兼容旧名称
    legacy_map = {
        "csu-deepseek[1m]": ("csu", "DeepSeek-V4-Flash"),
        "csu-deepseek": ("csu", "DeepSeek-V4-Flash"),
        "csu-deepseek-thinking[1m]": ("csu", "DeepSeek-V4-Flash"),
        "csu-deepseek-thinking": ("csu", "DeepSeek-V4-Flash"),
        "csu-qwen[256k]": ("csu", "Qwen3.6-35B-A3B"),
        "csu-qwen": ("csu", "Qwen3.6-35B-A3B"),
        "mimo-v2.5-pro[1m]": ("mimo", "mimo-v2.5-pro"),
        "mimo-v2.5[1m]": ("mimo", "mimo-v2.5"),
    }
    model_map.update(legacy_map)

    return model_map


# 动态构建 MODEL_MAP
MODEL_MAP = build_model_map()
DEFAULT_MODEL = list(MODEL_MAP.keys())[0] if MODEL_MAP else "deepseek-v3"
# ===================================


def convert_anthropic_tools(tools):
    """Anthropic tools → OpenAI tools"""
    openai_tools = []
    for tool in tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
            }
        })
    return openai_tools


def anthropic_to_openai(body: dict) -> dict:
    """Anthropic messages API → OpenAI chat completions API"""
    messages = []

    # system 消息
    system = body.get("system", "")
    if system:
        if isinstance(system, list):
            system_text = "\n".join(b.get("text", "") for b in system if b.get("type") == "text")
        else:
            system_text = system
        messages.append({"role": "system", "content": system_text})

    for msg in body.get("messages", []):
        role = msg["role"]
        content = msg.get("content", "")

        if isinstance(content, str):
            messages.append({"role": role, "content": content})
            continue

        if isinstance(content, list):
            # ---- assistant 消息：可能包含 tool_use ----
            if role == "assistant":
                text_parts = []
                tool_calls = []
                for i, block in enumerate(content):
                    if block.get("type") == "text":
                        text_parts.append(block["text"])
                    elif block.get("type") == "tool_use":
                        tool_calls.append({
                            "id": block["id"],
                            "type": "function",
                            "function": {
                                "name": block["name"],
                                "arguments": json.dumps(block.get("input", {})),
                            }
                        })
                msg_out = {"role": "assistant"}
                if text_parts:
                    msg_out["content"] = "\n".join(text_parts)
                else:
                    msg_out["content"] = None
                if tool_calls:
                    msg_out["tool_calls"] = tool_calls
                messages.append(msg_out)

            # ---- user 消息：可能包含 tool_result 和 image ----
            elif role == "user":
                text_parts = []
                image_parts = []
                tool_msgs = []
                for block in content:
                    if block.get("type") == "text":
                        text_parts.append(block["text"])
                    elif block.get("type") == "image":
                        src = block.get("source", {})
                        if src.get("type") == "base64":
                            media_type = src.get("media_type", "image/png")
                            data = src.get("data", "")
                            image_parts.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:{media_type};base64,{data}"}
                            })
                    elif block.get("type") == "tool_result":
                        result_content = block.get("content", "")
                        if isinstance(result_content, list):
                            result_text = "\n".join(
                                b.get("text", "") for b in result_content if b.get("type") == "text"
                            )
                        else:
                            result_text = str(result_content)
                        is_error = block.get("is_error", False)
                        tool_msgs.append({
                            "role": "tool",
                            "tool_call_id": block.get("tool_use_id", ""),
                            "content": f"[Error] {result_text}" if is_error else result_text,
                        })
                if image_parts:
                    # 多模态：text + image_url
                    msg_content = []
                    if text_parts:
                        msg_content.append({"type": "text", "text": "\n".join(text_parts)})
                    msg_content.extend(image_parts)
                    messages.append({"role": "user", "content": msg_content})
                elif text_parts:
                    messages.append({"role": "user", "content": "\n".join(text_parts)})
                messages.extend(tool_msgs)

            else:
                messages.append({"role": role, "content": str(content)})
        else:
            messages.append({"role": role, "content": str(content)})

    req_model = body.get("model", DEFAULT_MODEL)
    if req_model not in MODEL_MAP:
        raise ValueError(f"Unknown model: {req_model}. Available: {', '.join(MODEL_MAP.keys())}")
    upstream_name, upstream_model = MODEL_MAP[req_model]

    openai_req = {
        "model": upstream_model,
        "messages": messages,
        "max_tokens": body.get("max_tokens", 4096),
        "stream": body.get("stream", False),
    }

    # 流式时请求返回 usage
    if openai_req["stream"]:
        openai_req["stream_options"] = {"include_usage": True}

    # 思考模式：Anthropic thinking → DeepSeek enable_thinking + budget_tokens
    # 只在 DeepSeek 上游模型上设置 thinking 参数（Qwen 不支持）
    upstream_map = MODEL_MAP.get(req_model, (None, None))
    upstream_model_name = upstream_map[1] if upstream_map else req_model
    is_deepseek = upstream_model_name and "DeepSeek" in upstream_model_name
    is_thinking = "-thinking" in req_model
    if not is_thinking:
        thinking = body.get("thinking", {})
        is_thinking = thinking.get("type") == "enabled"
    if ENABLE_THINKING and is_thinking and is_deepseek:
        thinking_cfg = body.get("thinking", {})
        openai_req["enable_thinking"] = True
        openai_req["budget_tokens"] = thinking_cfg.get("budget_tokens", 4096)

    # 工具定义
    if "tools" in body:
        openai_req["tools"] = convert_anthropic_tools(body["tools"])

    # tool_choice 转换
    if "tool_choice" in body:
        tc = body["tool_choice"]
        tc_type = tc.get("type", "auto")
        if tc_type == "auto":
            openai_req["tool_choice"] = "auto"
        elif tc_type == "any":
            openai_req["tool_choice"] = "required"
        elif tc_type == "tool":
            openai_req["tool_choice"] = {"type": "function", "function": {"name": tc.get("name", "")}}
        elif tc_type == "none":
            openai_req["tool_choice"] = "none"

    if "temperature" in body:
        openai_req["temperature"] = body["temperature"]
    if "top_p" in body:
        openai_req["top_p"] = body["top_p"]
    if "stop_sequences" in body:
        openai_req["stop"] = body["stop_sequences"]

    return openai_req


def openai_response_to_anthropic(openai_resp: dict, model: str) -> dict:
    """OpenAI chat completion → Anthropic message"""
    choice = openai_resp.get("choices", [{}])[0]
    msg = choice.get("message", {})
    finish = choice.get("finish_reason", "stop")

    content_blocks = []

    # 思考内容 (DeepSeek reasoning_content → Anthropic thinking block)
    reasoning = msg.get("reasoning_content", "")
    if reasoning:
        content_blocks.append({"type": "thinking", "thinking": reasoning})

    # 文本内容
    text = msg.get("content", "")
    if text:
        content_blocks.append({"type": "text", "text": text})

    # 工具调用
    tool_calls = msg.get("tool_calls", [])
    for tc in tool_calls:
        func = tc.get("function", {})
        try:
            args = json.loads(func.get("arguments", "{}"))
        except json.JSONDecodeError:
            args = {}
        content_blocks.append({
            "type": "tool_use",
            "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:24]}"),
            "name": func.get("name", ""),
            "input": args,
        })

    if not content_blocks:
        content_blocks.append({"type": "text", "text": ""})

    stop_reason_map = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "end_turn",
    }

    usage = openai_resp.get("usage", {})
    anthropic_usage = {
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0),
    }
    anthropic_usage.update({k: v for k, v in usage.items() if k not in ("prompt_tokens", "completion_tokens")})

    return {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "content": content_blocks,
        "model": model,
        "stop_reason": stop_reason_map.get(finish, "end_turn"),
        "stop_sequence": None,
        "usage": anthropic_usage,
    }


def make_sse(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


@app.post("/v1/messages")
async def proxy(request: Request):
    body = await request.json()
    model = body.get("model", DEFAULT_MODEL)

    # 查找 upstream
    upstream_name, upstream_model = MODEL_MAP.get(model, (None, None))
    if not upstream_name:
        return JSONResponse(
            {"type": "error", "error": {"type": "invalid_request_error", "message": f"Unknown model: {model}"}},
            status_code=400,
        )

    upstream = UPSTREAMS[upstream_name]
    protocol = upstream["protocol"]
    body["model"] = upstream_model

    print(f"[REQ] model={model} → {upstream_name}/{upstream_model} protocol={protocol} stream={body.get('stream')}")

    headers = {
        "Authorization": f"Bearer {upstream['key']}",
        "Content-Type": "application/json",
    }

    if protocol == "anthropic":
        # Anthropic 协议：URL 是基础部分如 /anthropic，拼接 /v1/messages
        url = f"{upstream['url']}/v1/messages"
        if body.get("stream"):
            return StreamingResponse(
                anthropic_passthrough_stream(url, body, headers),
                media_type="text/event-stream",
            )
        else:
            try:
                async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                    resp = await client.post(url, json=body, headers=headers)
                    return JSONResponse(resp.json(), status_code=resp.status_code)
            except Exception as e:
                return JSONResponse(
                    {"type": "error", "error": {"type": "api_error", "message": str(e)}},
                    status_code=500,
                )
    else:
        # OpenAI 协议：URL 是基础部分如 /v1，拼接 /chat/completions
        openai_url = f"{upstream['url']}/chat/completions"
        openai_req = anthropic_to_openai(body)
        if body.get("stream"):
            return StreamingResponse(
                stream_handler(openai_req, model, headers, openai_url),
                media_type="text/event-stream",
            )
        else:
            try:
                async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                    resp = await client.post(openai_url, json=openai_req, headers=headers)
                    openai_resp = resp.json()
                    logger.info(f"[OpenAI resp] {json.dumps(openai_resp, ensure_ascii=False)[:500]}")
                    anthropic_resp = openai_response_to_anthropic(openai_resp, model)
                    return JSONResponse(anthropic_resp)
            except Exception as e:
                return JSONResponse(
                    {"type": "error", "error": {"type": "api_error", "message": str(e)}},
                    status_code=500,
                )


async def anthropic_passthrough_stream(url: str, body: dict, headers: dict):
    """Anthropic 协议流式透传"""
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            async with client.stream("POST", url, json=body, headers=headers) as resp:
                if resp.status_code >= 400:
                    error_body = await resp.aread()
                    logger.error(f"Anthropic upstream returned {resp.status_code}")
                    err_data = json.dumps({"type": "error", "error": {"type": "api_error", "message": f"Upstream {resp.status_code}: {error_body.decode()}"}})
                    yield f"event: errordata: {err_data}\n\n"
                    return
                async for line in resp.aiter_lines():
                    if line:
                        yield line + "\n"
    except Exception as e:
        logger.error(f"Anthropic passthrough error: {e}")
        yield f"event: error\ndata: {json.dumps({'type': 'error', 'error': {'type': 'api_error', 'message': str(e)}})}\n\n"



async def stream_handler(openai_req, model, headers, upstream_url):
    """流式响应生成器，支持工具调用"""
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"

    yield make_sse("message_start", {
        "type": "message_start",
        "message": {
            "id": msg_id, "type": "message", "role": "assistant",
            "content": [], "model": model,
            "stop_reason": None, "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }
    })

    # 用于收集工具调用的增量
    tool_calls_buf = {}  # index -> {id, name, arguments}
    block_index = 0
    current_block_type = None  # "text", "tool_use", or "thinking"
    finish_reason = None
    thinking_started = False
    usage_data = {}

    def start_thinking_block():
        nonlocal current_block_type, block_index, thinking_started
        if current_block_type != "thinking":
            if current_block_type:
                yield make_sse("content_block_stop", {"type": "content_block_stop", "index": block_index})
                block_index += 1
            current_block_type = "thinking"
            thinking_started = True
            yield make_sse("content_block_start", {
                "type": "content_block_start", "index": block_index,
                "content_block": {"type": "thinking", "thinking": ""},
            })

    def start_text_block():
        nonlocal current_block_type, block_index
        if current_block_type != "text":
            if current_block_type:
                yield make_sse("content_block_stop", {"type": "content_block_stop", "index": block_index})
                block_index += 1
            current_block_type = "text"
            yield make_sse("content_block_start", {
                "type": "content_block_start", "index": block_index,
                "content_block": {"type": "text", "text": ""},
            })

    def start_tool_block(index, tool_id, name):
        nonlocal current_block_type, block_index
        if current_block_type:
            yield make_sse("content_block_stop", {"type": "content_block_stop", "index": block_index})
            block_index += 1
        current_block_type = "tool_use"
        yield make_sse("content_block_start", {
            "type": "content_block_start", "index": block_index,
            "content_block": {"type": "tool_use", "id": tool_id, "name": name, "input": {}},
        })

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            async with client.stream("POST", upstream_url, json=openai_req, headers=headers) as resp:
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    if chunk.get("usage"):
                        usage_data = chunk["usage"]

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})
                    finish_reason = choices[0].get("finish_reason") or finish_reason

                    # 思考内容 (DeepSeek reasoning_content)
                    reasoning = delta.get("reasoning_content")
                    if reasoning:
                        for ev in start_thinking_block():
                            yield ev
                        yield make_sse("content_block_delta", {
                            "type": "content_block_delta", "index": block_index,
                            "delta": {"type": "thinking_delta", "thinking": reasoning},
                        })

                    # 文本内容
                    text = delta.get("content")
                    if text:
                        for ev in start_text_block():
                            yield ev
                        yield make_sse("content_block_delta", {
                            "type": "content_block_delta", "index": block_index,
                            "delta": {"type": "text_delta", "text": text},
                        })

                    # 工具调用增量
                    for tc_delta in delta.get("tool_calls", []):
                        tc_idx = tc_delta.get("index", 0)
                        if tc_idx not in tool_calls_buf:
                            tc_id = tc_delta.get("id", f"toolu_{uuid.uuid4().hex[:24]}")
                            tc_name = tc_delta.get("function", {}).get("name", "")
                            tool_calls_buf[tc_idx] = {"id": tc_id, "name": tc_name, "arguments": ""}
                            for ev in start_tool_block(tc_idx, tc_id, tc_name):
                                yield ev
                        # 收集 arguments 片段
                        args_chunk = tc_delta.get("function", {}).get("arguments", "")
                        if args_chunk:
                            tool_calls_buf[tc_idx]["arguments"] += args_chunk
                            yield make_sse("content_block_delta", {
                                "type": "content_block_delta", "index": block_index,
                                "delta": {"type": "input_json_delta", "partial_json": args_chunk},
                            })

    except Exception as e:
        logger.error(f"Upstream error: {e}")
        for ev in start_text_block():
            yield ev
        yield make_sse("content_block_delta", {
            "type": "content_block_delta", "index": block_index,
            "delta": {"type": "text_delta", "text": f"[Error: {e}]"},
        })

    # 关闭当前 block
    if current_block_type:
        yield make_sse("content_block_stop", {"type": "content_block_stop", "index": block_index})

    # stop_reason + usage
    stop = "tool_use" if (finish_reason == "tool_calls" and tool_calls_buf) else "end_turn"
    yield make_sse("message_delta", {
        "type": "message_delta",
        "delta": {"stop_reason": stop, "stop_sequence": None},
        "usage": {
            "input_tokens": usage_data.get("prompt_tokens", 0),
            "output_tokens": usage_data.get("completion_tokens", 0),
        },
    })
    yield make_sse("message_stop", {"type": "message_stop"})


@app.get("/")
async def health():
    return {"status": "ok", "models": list(MODEL_MAP.keys())}


@app.get("/v1/models")
async def list_models():
    return {
        "data": [{"id": name, "object": "model", "owned_by": upstream} for name, (upstream, _) in MODEL_MAP.items()]
    }


if __name__ == "__main__":
    print(f"API Bridge running on http://localhost:{PORT}")
    for name, cfg in UPSTREAMS.items():
        print(f"  [{name}] {cfg['url']} ({cfg['protocol']})")
    print(f"Models: {', '.join(MODEL_MAP.keys())}")
    uvicorn.run(app, host=BIND_HOST, port=PORT)
