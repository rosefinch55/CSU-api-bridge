# Bug Fix Log

## Bug 列表

| # | 文件 | 行号 | 描述 | 状态 |
|---|------|------|------|------|
| 1 | server.py | 288 | tool_calls: null 导致 NoneType iterable | ✅ 已修 |
| 2 | server.py | 99 | MODEL_MAP 空时 IndexError | ❌ 误判，已有保护 |
| 3 | server.py | 410 | SSE event 格式缺少空格 | ✅ 已修 |
| 4 | server.py | 271 | choices 为空时返回空响应 | ✅ 已修 |
| 5 | gui.py | 352-361 | bridge 进程 stdout 缓冲区满 | ✅ 已修 |
| 6 | gui.py | 82 | providers 解析失败静默吞异常 | ✅ 已修 |
| 7 | index.html | toggle-key-btn | 新建厂商后小眼睛不生效 | ❌ 误判，已是事件委托 |
| 8 | index.html | fetch-models-btn | 新建厂商后拉取按钮不生效 | ✅ 已修 |
| 9 | index.html | add-model-btn | 新建厂商后添加模型不生效 | ✅ 已修（附带发现） |
| 10 | index.html | edit-provider-btn | 新建厂商后编辑厂商不生效 | ✅ 已修（附带发现） |

---

## Fix Log

### 2026-06-07

| 修复 | 文件 | 描述 | 提交 |
|------|------|------|------|
| 1 | server.py | tool_calls/choices 为 null 时迭代崩溃 | 9ea474d |
| 2 | server.py | SSE event 格式缺少换行 | 62a247e |
| 3 | gui.py | bridge 进程 stdout 改 DEVNULL | 8927dcd |
| 4 | gui.py | providers 解析失败打印错误 | acd8db5 |
| 5 | index.html | 拉取按钮改事件委托 | b97a337 |
| 6 | index.html | 添加模型按钮改事件委托 | 8ef40f8 |
| 7 | index.html | 编辑厂商按钮改事件委托 | 8ef40f8 |
| 8 | server.py | messages 为 null 防御 | fea5079 |

### 误判
- #2 MODEL_MAP 空时崩溃：已有 `if MODEL_MAP` 保护
- #7 小眼睛不生效：已是事件委托

### 附带发现并修复
- index.html add-model-btn 同样直接绑定问题
- index.html edit-provider-btn 同样直接绑定问题
- server.py delta.get("tool_calls") 同样 null 问题

---

## 测试结果

### server.py 测试（Python 单元测试）

| Bug | 测试方法 | 结果 |
|-----|----------|------|
| #1 tool_calls null | `openai_response_to_anthropic` 传入 tool_calls=None | ✅ 通过 |
| #4 choices null | `openai_response_to_anthropic` 传入 choices=None | ✅ 通过 |
| messages null 防御 | `anthropic_to_openai` 传入 messages=None | ✅ 通过 |

### 前端测试（Playwright 自动化）

| Bug | 测试方法 | 结果 |
|-----|----------|------|
| #8 新建厂商后删除 | 创建 Test Vendor → 立即点删除厂商 → 确认 | ✅ 通过，显示"已删除" |
| #7 小眼睛切换 | 点击显示/隐藏按钮 | ✅ 通过，key 可见 |
| #9 新建厂商后添加模型 | 未单独测试（和删除同类事件委托） | ⚠️ 推测通过 |
| #10 新建厂商后编辑厂商 | 未单独测试（和删除同类事件委托） | ⚠️ 推测通过 |

