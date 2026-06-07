# API Bridge

Claude Code CLI 协议桥接服务。接收 Anthropic 格式请求，转发到任意后端 API。

## 两种模式

### 1. OpenAI 兼容 → Anthropic（以 CSU 为例）

适用于 OpenAI 兼容接口（DeepSeek、Qwen、vLLM 等）。

```
Claude Code  →  apibridge  →  CSU (OpenAI 协议)
(Anthropic)     转换层       (DeepSeek / Qwen)
```

自动处理：
- 消息格式转换（system / tool_use / tool_result / 图片）
- 工具定义转换（input_schema → parameters）
- 流式 SSE 增量同步

### 2. Anthropic 直传（以小米为例）

适用于原生 Anthropic 兼容接口（小米 mimo、第三方代理等）。

```
Claude Code  →  apibridge  →  小米 mimo (Anthropic 协议)
(Anthropic)     透传           (mimo-v2.5 / mimo-v2.5-pro)
```

请求直接转发，不做格式转换。

## 快速启动

### 1. 安装依赖

```bash
pip install fastapi uvicorn httpx python-dotenv aiohttp jinja2
```

### 2. 配置

复制 `.env.example` 为 `.env`，填入你的 API key：

```bash
cp .env.example .env
```

编辑 `.env`：

```env
CSU_URL=https://api.chat.csu.edu.cn/v1/chat/completions
CSU_KEY=sk-your-key-here

MIMO_URL=https://token-plan-cn.xiaomimimo.com/anthropic
MIMO_KEY=tp-your-key-here

PORT=4000
ENABLE_THINKING=false
REQUEST_TIMEOUT=300
BIND_HOST=0.0.0.0
```

> **注意**: 默认绑定 `0.0.0.0`（所有网卡）。如果在公网服务器上运行，建议设置 `BIND_HOST=127.0.0.1`。

### 3. 启动

#### 命令行模式

```bash
# CSU DeepSeek（OpenAI 转换模式）
scripts/start-csu.bat

# CSU DeepSeek Thinking（推理模式）
scripts/start-csu-thinking.bat

# CSU Qwen（OpenAI 转换模式）
scripts/start-csu-qwen.bat

# 小米 mimo v2.5-pro（直传模式）
scripts/start-mimo.bat

# 小米 mimo v2.5（直传模式）
scripts/start-xiaomi.bat
```

CSU 系列脚本会自动启动 bridge 服务（端口 4000），然后启动 Claude Code。
小米系列直连，不经过 bridge。

#### GUI 模式

```bash
scripts/start-gui.bat
```

启动 Web 控制台 `http://localhost:4000`，支持：
- 可视化配置厂商和模型
- 一键拉取模型列表
- 启停 Bridge 和 Claude
- 实时日志查看

## 项目结构

```
apibridge/
├── server.py          # Bridge 服务端
├── gui.py             # Web 控制台后端
├── providers.json     # 厂商配置（自动生成）
├── .env               # 环境变量配置
├── .env.example       # 配置模板
├── templates/
│   └── index.html     # 控制台前端
└── scripts/
    ├── start-csu.bat
    ├── start-csu-thinking.bat
    ├── start-csu-qwen.bat
    ├── start-mimo.bat
    ├── start-xiaomi.bat
    └── start-gui.bat
```

## 端点

| 路径 | 说明 |
|------|------|
| `GET /` | 健康检查 |
| `POST /v1/messages` | 主代理端点 |
| `GET /v1/models` | 模型列表 |
| `GET /gui` | Web 控制台 |

## License

MIT
