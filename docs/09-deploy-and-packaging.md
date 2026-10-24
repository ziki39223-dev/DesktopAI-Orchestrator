# 部署与打包（P3 编写，此处为占位骨架）

> 状态：⬜ P3 阶段填充。骨架先固定章节，避免届时边写边想。

## 1. 打包（开发机）
- [ ] 文件夹打包：拷贝清单、排除项（`.venv`、`logs`、`config.local.yaml`、`__pycache__`）
- [ ] PyInstaller 单文件 exe：`--onefile`、hidden-import 清单、体积与启动耗时实测
- [ ] 打包后可运行性自检（在纯净目录解压试跑）

## 2. 迁移到工作机
- [ ] 环境判定：Python 3.12 是否存在；不存在则走 exe 路线
- [ ] 依赖安装：`requirements.txt` +（real 模式）`requirements-real.txt`
- [ ] 首次启动：`start_sse.bat` 或 `start_stdio.bat`
- [ ] 配置调整：`mode: real`、端口、`auth_token`

## 3. 控件采集（关键步骤）
- [ ] 打开微软 `Inspect.exe`（UIA 模式）
- [ ] 逐客户端采集：输入框、发送按钮、输出区
- [ ] 回填 `window_rules.json`：`strategies` 按稳定性排序（automation_id → name → control_type → class_name）
- [ ] `reload_window_rules` 验证热重载生效

## 4. 真机验证清单（每次发版勾选）
- [ ] `list_target_windows` 三客户端全部 `ready=true`
- [ ] `send_prompt` 后窗口内实际出现 prompt（含结束标记约定）
- [ ] `fetch_output` 能读到结束标记，`status=completed`
- [ ] 客户端最小化 / 后台时仍能读写（记录捕获三态结论）
- [ ] 异常场景：关掉某客户端后调用 → `WINDOW_NOT_FOUND` 而非崩溃

## 5. 回填到需求基线
实测数据回填 `01-requirements-baseline.md` §10：
窗口标题/类名实采值、三态捕获可用性、单轮典型耗时（用于设默认 `timeout_s`）。
