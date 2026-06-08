# API Bridge

Claude Code CLI 协议桥接服务。本工具专为 **CSU 大学云 API** 设计，同时支持小米 mimo 等其他后端。

CSU 是本工具的核心服务，硬编码在程序中，必须通过本地 Bridge 代理连接（CSU 接口为 OpenAI 协议，需要转换层）。

## 两种模式

### 1. OpenAI → Anthropic 转换（CSU）

```
Claude Code  →  apibridge (Bridge)  →  CSU API
(Anthropic)     协议转换              (DeepSeek / Qwen)
```

自动处理消息格式、工具定义、流式 SSE 的协议转换。

### 2. Anthropic 直传（小米）

```
Claude Code  →  apibridge  →  小米 mimo
(Anthropic)     透传           (mimo-v2.5)
```

请求直接转发，不做格式转换。

## 快速启动

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

创建 `.env` 文件：

```env
CSU_KEY=sk-your-csu-key
MIMO_KEY=tp-your-mimo-key

PORT=4000
GUI_PORT=4100
GUI_SELECTED_PROVIDER=csu
GUI_SELECTED_MODEL=DeepSeek-V4-Flash
```

### 3. 启动

```bash
# 命令行模式
scripts/start-csu.bat      # CSU DeepSeek
scripts/start-csu-qwen.bat # CSU Qwen
scripts/start-mimo.bat     # 小米 mimo

# GUI 模式
scripts/start-gui.bat      # Web 控制台 http://localhost:4100
```

CSU 脚本会自动启动 Bridge（端口 4000），然后启动 Claude Code。

## API Key 管理

### 存储位置

| 文件 | 用途 | 是否上传 git |
|------|------|-------------|
| `.env` | API key 初始存储 | 否（.gitignore） |
| `providers.json` | 厂商配置 + 用户设置的 key | 否（.gitignore） |

### 读取逻辑

```
get_provider_key(provider, provider_id):
  1. providers.json 有 key → 使用
  2. providers.json 无 key → 读 .env 中的 {PROVIDER_ID}_KEY
```

### 写入逻辑

- **GUI 编辑厂商**：输入 key → 保存到 `providers.json`
- **GUI 保存配置**：不写入 key（只保存 URL、模型等）
- **首次使用**：`.env` 中配置 key，GUI 自动读取显示（标记"来自 .env"）

### 安全设计

- `providers.json` 和 `.env` 均不上传 git
- 编辑厂商时可设置新 key，保存到本地 `providers.json`
- 未设置 key 时自动 fallback 到 `.env`

## CSU 硬编码说明

CSU 大学云是本工具的核心服务，以下配置硬编码在 `gui.py` 的 `DEFAULT_PROVIDERS` 中：

```python
"csu": {
    "name": "CSU 大学云",
    "requires_bridge": True,  # CSU 必须走桥接
    "url": "https://api.chat.csu.edu.cn/v1",
    "key": "",  # 从 .env 读取 CSU_KEY
    "models_endpoint": "/models",
}
```

硬编码原因：
- 本工具专为 CSU API 设计
- CSU 接口为 OpenAI 协议，必须通过 Bridge 转换
- URL、协议类型等固定不变

## 项目结构

```
apibridge/
├── server.py          # Bridge 服务端（端口 4000）
├── gui.py             # Web 控制台后端（端口 4100）
├── providers.json     # 厂商配置（自动生成，不上传 git）
├── .env               # API key 和环境变量（不上传 git）
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
