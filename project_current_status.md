# Auto Bench 项目当前进展

更新时间：2026-05-09

## 1. 项目定位

Auto Bench 是面向竞品车对标活动的 Windows 桌面端工具，代码仓库位于 `auto_bench-master`，GitHub 远端为 `https://github.com/Koo4214/auto_bench.git`。

当前主线仍然是车端本地闭环：测试前配置、设备校准、现场录制、问题打点、本地回放、本地 triage 和数据整理。云端 OSS 上传已有雏形，但 TMS/TDM/KPI 云端页面与完整报表链路暂不作为当前阶段核心范围。

## 2. 上次推送基线

上次推送信息：

- 分支：`codex/update-active-safety-status`
- commit：`1bbc7ca Add active safety marking workflow`
- Draft PR：`https://github.com/Koo4214/auto_bench/pull/1`

上次推送主要完成了主动安全测试打点闭环，包括 `test_function`、`case_id`、主动安全专用打点面板、主动安全字段持久化、回放页展示/编辑，以及项目状态文档。

## 3. 距离上次推送的新增改动

### 3.1 测试功能体系重构

新增 `src/domain/test_functions.py`，统一管理测试功能枚举、默认值和旧名称兼容映射。

当前测试功能已扩展为：

- 行车测试-城区
- 行车测试-高速
- 行车测试-功能点检
- 行车测试-主观评价
- 园区测试（路试）
- 园区测试（场地）
- 泊车测试
- 主动安全测试

测试功能选择从校准页移动到设置页：

- `src/ui/pages/run_setup_page.py` 新增测试功能下拉框。
- 设置页加载配置时会恢复 `test_function`。
- 设置页收集表单时会写入规范化后的 `test_function`。
- `src/ui/pages/calibration_page.py` 移除了测试功能选择。
- `src/app/m1_app.py` 创建 run 时直接使用设置页表单里的 `test_function`。

### 3.2 run 与 issue 模型扩展

`src/domain/models.py`、`src/services/issue_service.py`、`src/services/run_session_service.py` 继续扩展 issue 字段，支持更多专项测试场景。

新增字段包括：

- `test_result`
- `severity_level`
- `parking_subject_scene`
- `parking_space_category`
- `recognition_result`
- `park_in_result`
- `park_out_result`
- `obstacle_result`
- `pose_result`
- `jerk_result`
- `parking_time_sec`
- `maneuver_count`

这些字段已贯通到 issue 创建、run session 打点入口、`issues.json` 和单 issue 快照保存。

### 3.3 园区测试支持

新增园区测试相关 schema：

- `campus_road_test`
- `campus_field_test`

录制页打点面板新增：

- 园区路试面板：道路类型、场景类型、问题类型、目标类型、本车动作、备注等。
- 园区场测面板：Case ID 搜索、用例详情展示、测试结果、备注。

新增 `src/ui/widgets/campus_field_case_ids.py`：

- 从 `caseid/园区测试场测caseid` 下的 xlsx 用例库读取 Case ID。
- 解析用例的工况、测试场景、自车行为、对象行为、期望结果。
- 支持 Case ID 搜索、补全和详情展示。

### 3.4 泊车测试支持

新增泊车测试 schema：

- `parking_test`

录制页打点面板新增泊车专项字段：

- 科目场景
- 车位分类
- Case ID
- 识别结果
- 泊入结果
- 泊出结果
- 避障结果
- 位姿结果
- 顿挫结果
- 泊车时间
- 揉库次数
- 备注

新增 `src/ui/widgets/parking_case_ids.py`：

- 从 `caseid/泊车caseID` 下的 xlsx 用例库读取泊车 Case ID。
- 按科目场景过滤 Case ID。
- 支持 Case ID 搜索、补全和详情展示。

### 3.5 高速 KPI 支持

新增高速 KPI schema：

- `highway_kpi_test`

新增 `src/ui/widgets/highway_kpi_tags.py`：

- 管理高速测试场景、问题描述、本车动作、严重程度。
- 回放页和打点页可复用同一套高速 KPI 标签。

录制页新增高速专项打点面板：

- 测试场景
- 问题描述
- 本车动作
- 严重程度
- 备注

### 3.6 打点编辑器扩展

`src/ui/widgets/issue_editor.py` 从上次的“通用 + 主动安全”扩展为多场景栈式面板：

- 通用问题面板
- 园区路试面板
- 园区场测面板
- 泊车面板
- 高速 KPI 面板
- 主动安全面板

`IssueEditorWidget.set_test_function()` 会根据当前 run 的测试功能自动切换对应面板。

### 3.7 回放页增强

`src/ui/pages/playback_page.py` 扩展较多，主要包括：

- issue 表格新增专项字段列：测试结果、科目场景、车位分类、识别/泊入/泊出/避障/位姿/顿挫、泊车时间、揉库次数、严重程度等。
- 筛选项新增专项字段。
- 根据 `marking_schema` 或当前 run 的 `test_function` 推断 issue 类型。
- 回放编辑区根据 issue 类型启用对应字段，避免不同专项字段混用。
- 支持园区场测、园区路试、高速 KPI、泊车、主动安全 issue 的编辑写回。
- 对旧数据做兼容处理，例如没有专项字段时仍可回退到通用字段展示。

### 3.8 本地配置变化

当前 `config.json` 有本地未提交变化：

- 新增 `test_function`
- `vehicle_id` 从 `TEST001` 改为 `APA`

该文件包含本机路径和测试车辆号，属于本地运行配置风险较高的文件，推送时建议继续谨慎处理，不默认提交。

## 4. 当前已具备能力

- 本地 run 创建、元数据保存、状态保存。
- RTK 串口采集与历史回放。
- WT901 BLE IMU 扫描、采集与历史回放。
- 双摄预览。
- FFmpeg 屏幕分段录制、拼接和 issue clip 生成。
- 通用问题打点。
- 主动安全测试打点。
- 园区路试/场测打点。
- 泊车测试打点。
- 高速 KPI 打点。
- 本地 run 回放、issue 表格、clip 播放、问题字段编辑和 JSON 写回。
- OSS 上传状态查询与上传进度弹窗雏形。

## 5. 当前验证情况

已完成：

- 在 `auto_bench-master` 下执行 `python -m compileall -q src`，源码编译检查通过。
- 对比了当前工作区与上次推送 commit `1bbc7ca` 的差异。
- 通过 `rg` 检查测试功能、schema、Case ID、泊车字段、高速 KPI 字段在模型、服务、录制页和回放页中的贯通情况。

未完成：

- 尚未做完整 GUI 冒烟测试。
- 尚未接入真实 RTK、真实 BLE IMU 和真实双摄做实车流程验证。
- 尚未验证多专项流程的端到端闭环：创建 run -> 打点 -> 停止录制 -> clip 生成 -> 回放编辑 -> JSON 写回。
- 尚未验证 PyInstaller 打包产物。

## 6. 当前风险与注意事项

- 根目录 `D:\Projects\auto_bench` 不是 git 仓库；Git 仓库在 `auto_bench-master` 下。
- 中文内容在当前终端读取时仍有乱码显示风险，建议通过编辑器和实际 UI 再确认文案显示。
- 新增 Case ID 解析依赖外部 xlsx 用例库目录和表头格式；如果文件名、目录或表头变化，需要同步调整解析逻辑。
- 多专项打点面板已通过编译，但 GUI 布局、字段启用/禁用、补全弹窗和回放编辑仍需实测。
- `config.json` 暂不建议直接推送本机车辆号和路径。
- 当前机器未安装 GitHub CLI `gh`；本地普通 `git push` 在沙盒中可能因 Windows/Git 凭据失败，需要使用已批准的沙盒外 `git push`。

## 7. 建议下一步

1. 先跑 GUI 冒烟测试，覆盖设置页测试功能选择，以及 5 类专项打点面板切换。
2. 用历史样例回放目录分别跑园区、泊车、高速、主动安全的无硬件流程。
3. 针对不同 `marking_schema` 准备样例 issue JSON，验证旧数据和新数据都能回放编辑。
4. 用真实 RTK、IMU、双摄做至少一条实车短流程。
5. 补充自动化测试，优先覆盖测试功能规范化、Case ID xlsx 解析、issue 持久化、回放编辑写回。
6. 修订 README，补充测试功能、用例库目录、OSS 环境变量和 GUI 冒烟测试说明。
