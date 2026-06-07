# API Bridge

Claude Code CLI 协议桥接服务。接收 Anthropic 格式请求，转发到任意后端 API。

**核心服务：CSU 大学云**（硬编码，必须走本地 Bridge 代理）。

## 两种模式

### 1. OpenAI 兼容 → Anthropic（CSU）

适用于 OpenAI 兼容接口（DeepSeek、Qwen、vLLM 等）。

```
Claude Code  →  apibridge  →  CSU (OpenAI 协议)
(Anthropic)     转换层       (DeepSeek / Qwen)
```

自动处理：
- 消息格式转换（system / tool_use / tool_result / 图片）
- 工具定义转换（input_schema → parameters）
- 流式 SSE 增量同步

### 2. Anthropic 直传（小米）

适用于原生 Anthropic 兼容接口（小米 mimo、第三方代理等）。

```
Claude Code  →  apibridge  →  小米 mimo (Anthropic 协议)
(Anthropic)     透传           (mimo-v2.5 / mimo-v2.5-pro)
```

请求直接转发，不做格式转换。

## 快速启动

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

创建 `.env` 文件，填入 API key：

```env
CSU_KEY=sk-your-key-here
MIMO_KEY=tp-your-key-here

PORT=4000
GUI_PORT=4100
ENABLE_THINKING=false
REQUEST_TIMEOUT=300
BIND_HOST=0.0.0.0
GUI_SELECTED_PROVIDER=csu
GUI_SELECTED_MODEL=DeepSeek-V4-Flash
```

> **安全提示**：API key 只存在 `.env` 中，`providers.json` 不存储 key（已加入 `.gitignore`）。

> **注意**: 默认绑定 `0.0.0.0`（所有网卡）。如果在公网服务器上运行，建议设置 `BIND_HOST=127.0.0.1`。

### 3. 启动

#### 命令行模式

```bash
# CSU DeepSeek
scripts/start-csu.bat

# CSU Qwen
scripts/start-csu-qwen.bat

# 小米 mimo
scripts/start-mimo.bat
```

CSU 系列脚本会自动启动 bridge 服务（端口 4000），然后启动 Claude Code。

#### GUI 模式

```bash
scripts/start-gui.bat
```

启动 Web 控制台 `http://localhost:4100`，支持：
- 可视化配置厂商和模型
- 一键拉取模型列表
- 启停 Bridge 和 Claude
- 实时日志查看
- API Key 从 `.env` 读取，编辑厂商时可设置新 key

## 项目结构

```
apibridge/
├── server.py          # Bridge 服务端（端口 4000）
├── gui.py             # Web 控制台后端（端口 4100）
├── providers.json     # 厂商配置（自动生成，不上传 git）
├── .env               # 环境变量和 API key（不上传 git）
├── requirements.txt   # Python 依赖
├── templates/
│   └── index.html     # 控制台前端
└── scripts/
    ├── start-csu.bat
    ├── start-csu-qwen.bat
    ├── start-mimo.bat
    └── start-gui.bat
```

## 端点

| 路径 | 说明 |
|------|------|
| `GET /` | 健康检查 |
| `POST /v1/messages` | 主代理端点 |
| `GET /v1/models` | 模型列表 |

## License

MIT
