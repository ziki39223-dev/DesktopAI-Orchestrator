# 目录分区（Directory Layout）

> 状态：Phase 0 · 目录已建立（`.gitkeep` 占位），业务代码在 Phase 1 起按本表落位。
> 规则：**目录按职责分区，文件按层归属，禁止跨层乱放。**

## 1. 顶层树

```
DesktopAI-Orchestrator/
├─ README.md                       项目门面：定位、边界、文档索引
├─ pyproject.toml · requirements.txt   依赖与打包元数据（Phase 1）
├─ .gitignore · .editorconfig      工程卫生（Phase 1）
├─ src/desktop_ai_orchestrator/    源码根（src-layout，避免测试期路径污染）
│  ├─ entry/                       进程入口：SSE / stdio 各一个
│  ├─ server/                      MCP Server 装配、能力注册、生命周期
│  ├─ tools/                       对外 4 个工具：入参校验 + 出参封装 + 错误映射
│  ├─ routers/                     mode 开关 → 后端选择
│  ├─ contracts/                   工具入参/出参/错误码（唯一真源）
│  ├─ config/                      config.yaml / window_rules.json 加载与校验
│  ├─ backends/mock/               Mock 后端（零 GUI 依赖）
│  ├─ backends/real/               Real 后端（UIA + 窗口捕获）
│  ├─ common/                      日志、错误、时间、重试等无业务工具
│  └─ observability/               结构化日志、耗时统计、日志落盘
├─ config/                         yaml / json 模板（随包分发）
├─ scripts/                        启动 bat、打包、自测脚本
├─ tests/unit | contract | e2e    三层测试，契约测试不依赖 GUI
├─ docs/                           文档体系（见 00-doc-map.md）
├─ docs/diagrams/                  分层图，一层一文件
└─ devtools/uia/                   工作机控件采集辅助脚本（只读探测，不进主流程）
```

## 2. 各目录职责与禁忌

| 目录 | 职责 | 允许依赖 | 禁止 |
| --- | --- | --- | --- |
| `entry/` | 解析启动参数、读配置、选传输、启动 Server | server、config | 写业务逻辑、直接调后端 |
| `server/` | 造 MCP Server 实例、注册工具、处理生命周期与优雅退出 | tools、contracts、observability | 直接调 backends |
| `tools/` | 入参校验、调后端、出参封装、异常→错误码映射 | routers、contracts | 出现 Windows API、出现 `mode == "real"` 判断 |
| `routers/` | 依据 `mode` 产出后端实例；后端统一接口契约 | backends、config、contracts | 写工具业务 |
| `contracts/` | pydantic 模型、错误码枚举、常量（如结束标记） | 仅标准库/pydantic | import 任何本项目上层模块 |
| `config/` | 加载 + 校验 yaml/json，热重载支撑 | contracts、common | 直接持有后端对象 |
| `backends/mock/` | 可预期模拟数据、延迟/失败注入 | contracts、common | import real 后端 |
| `backends/real/` | 枚举窗口、捕获、UIA 读写 | contracts、common、config | import tools/routers、被 mock 引用 |
| `common/` | 错误类型、重试、文本清洗、时间 | 标准库 | import 业务层 |
| `observability/` | 日志、耗时、任务追踪 ID | common、contracts | 业务判断 |
| `devtools/uia/` | 控件路径采集、窗口探测（工作机用） | 可自由依赖 Windows 库 | 被主服务 import |

## 3. 三个后端的文件级落位（Phase 1–2）

| 文件 | 阶段 | 说明 |
| --- | --- | --- |
| `contracts/tools.py` | 1 | 四工具入参/出参模型 |
| `contracts/errors.py` | 1 | 错误码枚举 + 结构化错误模型 |
| `contracts/constants.py` | 1 | `COMPLETION_MARKER = "【Agent任务完成】"` 等 |
| `routers/backend_router.py` | 1 | `get_backend(mode)`，返回统一 `Backend` 协议 |
| `backends/base.py` | 1 | 后端抽象接口（mock/real 共同实现） |
| `backends/mock/*.py` | 1 | 静态窗口清单、脚本化输出、延迟注入 |
| `server/app.py` | 1 | Server 装配与工具注册 |
| `entry/sse.py` / `entry/stdio.py` | 1 | 两个传输入口 |
| `backends/real/window_enum.py` | 2 | 窗口枚举与标题/类名匹配 |
| `backends/real/uia_driver.py` | 2 | 定位输入框、SetValue、触发发送、读输出 |
| `backends/real/capture.py` | 2 | DXGI / GraphicsCapture 窗口捕获 |
| `backends/real/resolver.py` | 2 | 按 `window_rules.json` 解析控件路径，带重试 |

## 4. 命名与落位纪律

1. 文件名一律 `snake_case`，一文件一职责；超过 ~300 行即拆分（对应 `TxtBar.*.cs` 那样的分文件习惯）。
2. 临时脚本/探测结果只写 `.ai-workspace-runtime/tmp/`（或项目内 `devtools/tmp/`，已在 gitignore 中排除），**不入库、不落工作区根**。
3. 任何“只用于开发机”的代码（mock 注入、调试探针）不得出现在 `backends/real/`。
4. 配置模板放在根 `config/`，运行期用户配置可在项目根 `config.local.yaml`（gitignore），加载优先级：环境变量 > `config.local.yaml` > `config/config.yaml`。
