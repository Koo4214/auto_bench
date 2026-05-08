# Auto Bench 项目当前进展

更新时间：2026-05-08

## 1. 项目定位

Auto Bench 是面向竞品车对标活动的 Windows 桌面端工具，代码仓库位于 `auto_bench-master`，当前远端为 `https://github.com/Koo4214/auto_bench.git`。

当前阶段目标是先把车端本地闭环做好：测试前配置、设备校准、现场录制、问题打点、本地回放、本地 triage 和数据整理。后续再在稳定的本地数据结构之上接入云端上传、报告引用、TMS/TDM/KPI 等链路。

技术栈以 Python + PyQt5 为主，结合 RTK 串口、WT901 BLE IMU、双摄预览、FFmpeg 录屏/切片、本地 JSON/CSV 存储，以及可选 OSS 上传。

## 2. 当前范围

当前主线仍是本地采集和回放闭环。

- 做：本地 run 创建、双摄预览、RTK/IMU 数据采集、屏幕录制、问题打点、clip 生成、本地回放、问题字段编辑、主动安全测试基础记录。
- 暂不做：TMS triage、TDM KPI 页面、4 路摄像头扩展、完整云端报表链路。
- 摄像头能力目前保持 2 路结构。
- 云端 OSS 上传已有雏形，但不是当前阶段核心验收链路。

## 3. 已具备能力

### 3.1 基础采集与记录

- 设置页支持输出路径、FFmpeg 路径、车辆信息、测试人员、城市等 run 基础元数据配置。
- 校准页支持 RTK 串口、RTK 波特率、IMU 蓝牙设备、IMU 方向轴、方向取反、样例回放目录、双摄设备选择。
- 录制页支持双摄状态展示、RTK/IMU 状态展示、方向盘角度、车速、横/纵向加速度、jerk 曲线和问题打点。
- 支持历史样例回放驱动，用于无实车/无传感器时做本地流程验证。
- 屏幕录制使用 FFmpeg 分段录制，停止录制后尝试拼接，并为 issue 生成前后窗口 clip。

### 3.2 本地数据组织

- run 数据按日期、车型、车辆编号和 run_id 组织。
- 已保存 `meta.json`、`status.json`、RTK raw/CSV、IMU raw/CSV、录屏分段、最终录屏、`issues.json` 和单 issue 快照。
- issue 支持独立 `issue_info.json` 快照，便于后续引用和 triage。

### 3.3 本地回放与 triage

- 回放页可扫描本地 run，展示 run 列表、issue 表格、打点 clip，并支持编辑问题字段。
- 回放列表能读取并展示 `test_function`，便于区分行车、泊车、主动安全等测试类型。
- issue 编辑后会写回 `issues.json` 和单 issue 快照，并标记 triage 状态与 triage 时间。

### 3.4 OSS 上传雏形

- `src/services/oss_upload_service.py` 从环境变量读取 `OSS_ACCESS_KEY_ID` 和 `OSS_ACCESS_KEY_SECRET`。
- 数据管理弹窗和上传进度弹窗已有 OSS 上传状态查询、上传完成标记和目标路径展示能力。
- 后续仍需补齐部署配置说明、失败重试策略和权限校验。

## 4. 最近实现重点

### 4.1 测试功能选择

- `RunMeta` 增加 `test_function` 字段，默认值为“行车-外部路测试”。
- 校准页已有测试功能下拉选项：
  - 行车-外部路测试
  - 行车-园区测试
  - 行车-高速测试
  - 泊车测试
  - 主动安全测试
- 主程序创建 run 时会把校准页选择的测试功能写入 run 元数据，并切换录制页打点面板。

### 4.2 issue 数据模型扩展

`IssueRecord` 已扩展以下字段：

- `case_id`
- `marking_schema`
- `active_safety_function`
- `active_safety_mode`
- `speed_kph`
- `takeover_result`
- `road_test_result`

这些字段已贯通到 `IssueService.create_issue()`、`RunSessionService.create_probe_issue()`、`issues.json` 和单 issue 快照保存逻辑。

### 4.3 主动安全打点面板

- 新增主动安全专用打点面板。
- 支持功能选择：AEB、FCW、RAEB、MEB、AES、LKA、LDW、IHB、TSR、DSM、DOW、BSD、RTCA。
- 支持“场测 / 路试”两类记录：
  - 场测：case ID、速度 kph、测试结果 pass/fail。
  - 路试：结果为正触发、误触发、漏触发。
- 支持备注输入。
- 当测试功能为“主动安全测试”时，录制页自动切换到主动安全打点面板；其他测试功能继续使用原有通用打点面板。

### 4.4 Case ID 支持

- 新增 `src/ui/widgets/active_safety_case_ids.py`，可从根目录 `caseid/主动安全caseid` 下的 xlsx 用例库提取 case ID。
- 主动安全打点面板支持按功能前缀和输入文本搜索 case ID，并提供补全候选。
- 录制时会统计当前 run 内各 case ID 已打点次数，并在面板上展示。
- 通用打点面板也保留可选 `Case ID` 字段，用于泊车、场地或其他用例绑定。

### 4.5 回放页增强

- issue 表格新增 Case ID、主动安全功能、模式、速度、结果、备注等列。
- 筛选项新增主动安全相关字段。
- 编辑区支持主动安全 issue 的专属字段编辑，并根据 `marking_schema` 区分通用问题和主动安全问题。
- 主动安全 issue 保存时会同步更新问题类型、本车操作、结果字段和 triage 信息。

### 4.6 辅助验证脚本

- `scripts/verify_window.py`
- `scripts/verify_window.ps1`
- `scripts/verify_window.cmd`

这些脚本用于辅助启动和检查窗口状态，便于后续做 GUI 冒烟测试。

## 5. 当前验证情况

已完成：

- 在 `auto_bench-master` 下执行 `python -m compileall -q src`，源码编译检查通过。
- 使用 `rg` 核对 `test_function`、`case_id`、主动安全字段在模型、服务、录制页、回放页和打点组件中的贯通情况。
- 确认代码仓库远端为 GitHub：`Koo4214/auto_bench`。

未完成：

- 尚未做完整 GUI 冒烟测试。
- 尚未接入真实 RTK、真实 BLE IMU 和真实双摄做实车流程验证。
- 尚未验证从“创建 run -> 主动安全打点 -> 停止录制 -> clip 生成 -> 回放编辑 -> JSON 写回”的完整端到端流程。
- 尚未验证 PyInstaller 打包产物。

## 6. 当前风险与注意事项

- 根目录 `D:\Projects\auto_bench` 不是 git 仓库；代码仓库在 `auto_bench-master` 下。
- 为了让 GitHub 仓库也包含状态文档，建议在 `auto_bench-master` 中同步保留一份 `project_current_status.md`。
- 部分中文内容在终端读取时出现乱码显示，建议后续通过编辑器和实际 UI 再确认文案编码与显示效果。
- 主动安全功能目前已通过编译检查，但还需要 GUI 流程验证，尤其是打点面板切换、case ID 补全、路试/场测字段互斥保存、回放编辑写回。
- Case ID 解析依赖根目录 `caseid/主动安全caseid` 下的 xlsx 文件命名和表头格式；如果用例库目录或表头变化，需要同步调整解析逻辑。
- `config.json` 当前车辆编号为 `AEB002`，看起来像本地测试配置变更，推送时应谨慎处理。
- 当前机器未检测到 GitHub CLI `gh`，因此无法使用 `gh auth status` 做 CLI 认证检查，也无法走完整 draft PR 自动创建流程。

## 7. 建议下一步

1. 先跑 GUI 冒烟测试，重点确认校准页测试功能选择、录制页打点面板切换、主动安全打点创建和回放页展示。
2. 用历史样例回放目录跑一条无硬件端到端流程，验证 JSON、clip 和回放编辑写回。
3. 接入真实 RTK、WT901 BLE IMU 和双摄，验证采集稳定性、掉线提示和录屏切片。
4. 对历史 issue JSON 做兼容性检查，确认旧数据没有主动安全字段时仍能正常回放和编辑。
5. 补充自动化测试，优先覆盖 run 创建、issue 创建、Case ID 解析、playback update 和 clip 窗口计算。
6. 修订 README 和项目计划文档的中文编码/展示问题，并补充 OSS 环境变量配置说明。
7. 在 GUI 流程稳定后再做 PyInstaller 打包验证和现场试用版本冻结。
