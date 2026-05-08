from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.services.playback_service import PlaybackService
from src.ui.i18n import zh
from src.ui.widgets.active_safety_case_ids import ACTIVE_SAFETY_FUNCTIONS
from src.ui.widgets.ffmpeg_video_widget import FfmpegVideoWidget
from src.ui.widgets.issue_editor import (
    CAMPUS_EGO_ACTIONS,
    CAMPUS_PROBLEM_OPTIONS,
    CAMPUS_ROAD_MARKING_SCHEMA,
    CAMPUS_ROAD_TEST_FUNCTION,
    CAMPUS_ROAD_TYPES,
    CAMPUS_SCENE_TYPES,
    CAMPUS_TARGET_TYPES,
    PROBLEM_OPTIONS,
)


LEGACY_ROAD_TYPES = [
    "Urban main road",
    "Urban expressway",
    "Urban narrow road",
    "Campus ground",
    "Campus garage",
]

LEGACY_SCENE_TYPES = [
    "Straight",
    "Curve",
    "Split / merge",
    "Right turn lane",
    "Main / side road switch",
    "U-turn",
    "Protected straight",
    "Protected left",
    "Protected right",
    "Unprotected straight",
    "Unprotected left",
    "Unprotected right",
    "Roundabout",
    "Toll station",
    "Construction",
    "Gate entry / exit",
    "Before campus",
    "After campus",
    "Drive-to-park in",
    "Drive-to-park out",
]

LEGACY_TARGET_TYPES = [
    "Passenger car",
    "Truck",
    "Bus",
    "Construction vehicle",
    "Special vehicle",
    "VRU pedestrian",
    "VRU two-wheeler",
    "VRU special",
    "Obstacle",
    "None",
]

LEGACY_EGO_ACTIONS = [
    "Safety takeover",
    "Experience takeover",
    "No action",
]


class PlaybackPage(QWidget):
    TABLE_COLUMNS = [
        ("序号", "seq_no", 48),
        ("时间", "issue_time_text", 128),
        ("经纬度", "latlon", 102),
        ("Case ID", "case_id", 96),
        ("功能", "active_safety_function", 72),
        ("模式", "active_safety_mode", 64),
        ("速度(kph)", "speed_kph", 82),
        ("结果", "active_safety_result", 92),
        ("道路类型", "road_type", 112),
        ("场景类型", "scene_type", 112),
        ("问题类型", "problem_type", 128),
        ("目标类型", "target_type", 112),
        ("本车操作", "ego_action", 124),
        ("备注", "comment", 160),
        ("triage", "triage", 76),
        ("triage_time", "triage_time", 138),
    ]
    FILTER_FIELDS = [
        ("道路类型", "road_type"),
        ("场景类型", "scene_type"),
        ("问题大类", "problem_tab"),
        ("问题类型", "problem_type"),
        ("目标类型", "target_type"),
        ("本车操作", "ego_action"),
        ("主动安全功能", "active_safety_function"),
        ("主动安全模式", "active_safety_mode"),
        ("主动安全结果", "active_safety_result"),
        ("triage", "triage"),
    ]

    def __init__(self, playback_service: PlaybackService) -> None:
        super().__init__()
        self.playback_service = playback_service
        self.current_run: Optional[Dict[str, object]] = None
        self.current_issue: Optional[Dict[str, object]] = None
        self.all_issues: List[Dict[str, object]] = []
        self.visible_issues: List[Dict[str, object]] = []
        self.current_clip_path: Optional[Path] = None
        self.edit_mode = False

        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        root.addWidget(self.left_panel)

        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        root.addWidget(self.right_panel)

        left_layout.addWidget(QLabel("回放 / 编辑"))

        path_row = QHBoxLayout()
        self.output_path = QLineEdit()
        self.browse_btn = QPushButton("浏览")
        self.refresh_btn = QPushButton("刷新 run")
        path_row.addWidget(QLabel("输出路径"))
        path_row.addWidget(self.output_path, 1)
        path_row.addWidget(self.browse_btn)
        path_row.addWidget(self.refresh_btn)
        left_layout.addLayout(path_row)

        self.run_list = QListWidget()
        left_layout.addWidget(self.run_list, 1)

        filter_row = QHBoxLayout()
        self.filter_field_box = QComboBox()
        for label, key in self.FILTER_FIELDS:
            self.filter_field_box.addItem(label, key)
        self.filter_value_box = QComboBox()
        self.filter_value_box.addItem('全部', '')
        self.clear_filter_btn = QPushButton('清空')
        filter_row.addWidget(QLabel('筛选'))
        filter_row.addWidget(self.filter_field_box)
        filter_row.addWidget(self.filter_value_box, 1)
        filter_row.addWidget(self.clear_filter_btn)
        left_layout.addLayout(filter_row)

        self.issue_count_label = QLabel('可见问题数：0')
        left_layout.addWidget(self.issue_count_label)

        self.issue_table = QTableWidget(0, len(self.TABLE_COLUMNS))
        self.issue_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.issue_table.setSelectionMode(QTableWidget.SingleSelection)
        self.issue_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.issue_table.setAlternatingRowColors(True)
        self.issue_table.verticalHeader().setVisible(False)
        self.issue_table.setHorizontalHeaderLabels([title for title, _key, _width in self.TABLE_COLUMNS])
        self.issue_table.setSortingEnabled(True)
        header = self.issue_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Fixed)
        header.setStretchLastSection(False)
        header.setSectionsMovable(False)
        for index, (_title, _key, width) in enumerate(self.TABLE_COLUMNS):
            self.issue_table.setColumnWidth(index, width)
        left_layout.addWidget(self.issue_table, 2)

        edit_box = QWidget()
        edit_layout = QFormLayout(edit_box)
        edit_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.road_type = QComboBox()
        self._fill_combo(self.road_type, LEGACY_ROAD_TYPES)
        self.scene_type = QComboBox()
        self._fill_combo(self.scene_type, LEGACY_SCENE_TYPES)
        self.problem_tab = QComboBox()
        self._fill_combo(self.problem_tab, list(PROBLEM_OPTIONS.keys()))
        self.problem_type = QComboBox()
        self.problem_tab.currentIndexChanged.connect(self._refresh_problem_types)
        self._refresh_problem_types(self.problem_tab.currentIndex())
        self.target_type = QComboBox()
        self._fill_combo(self.target_type, LEGACY_TARGET_TYPES)
        self.ego_action = QComboBox()
        self._fill_combo(self.ego_action, LEGACY_EGO_ACTIONS)
        self.case_id = QLineEdit()
        self.active_safety_function = QComboBox()
        self._fill_combo(self.active_safety_function, list(ACTIVE_SAFETY_FUNCTIONS), include_empty=True)
        self.active_safety_mode = QComboBox()
        self._fill_combo(self.active_safety_mode, ["场测", "路试"], include_empty=True)
        self.speed_kph = QLineEdit()
        self.takeover_result = QComboBox()
        self._fill_combo(self.takeover_result, ["pass", "fail"], include_empty=True)
        self.road_test_result = QComboBox()
        self._fill_combo(self.road_test_result, ["正触发", "误触发", "漏触发"], include_empty=True)
        self.comment = QTextEdit()
        self.comment.setFixedHeight(56)
        self.comment.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for combo in [
            self.road_type,
            self.scene_type,
            self.problem_tab,
            self.problem_type,
            self.target_type,
            self.ego_action,
            self.active_safety_function,
            self.active_safety_mode,
            self.takeover_result,
            self.road_test_result,
        ]:
            combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(16)
            combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        edit_layout.addRow("道路类型", self.road_type)
        edit_layout.addRow("场景类型", self.scene_type)
        edit_layout.addRow("问题大类", self.problem_tab)
        edit_layout.addRow("问题类型", self.problem_type)
        edit_layout.addRow("目标类型", self.target_type)
        edit_layout.addRow("本车操作", self.ego_action)
        edit_layout.addRow("Case ID", self.case_id)
        edit_layout.addRow("主动安全功能", self.active_safety_function)
        edit_layout.addRow("主动安全模式", self.active_safety_mode)
        edit_layout.addRow("速度(kph)", self.speed_kph)
        edit_layout.addRow("测试结果", self.takeover_result)
        edit_layout.addRow("路试结果", self.road_test_result)
        edit_layout.addRow("备注", self.comment)
        left_layout.addWidget(edit_box)

        button_row = QHBoxLayout()
        self.prev_issue_btn = QPushButton('上一个问题')
        self.next_issue_btn = QPushButton('下一个问题')
        self.play_btn = QPushButton("播放片段")
        self.open_btn = QPushButton("外部打开")
        self.edit_btn = QPushButton("编辑")
        self.save_btn = QPushButton("保存")
        self.back_btn = QPushButton("返回")
        self.save_btn.setEnabled(False)
        for button in [self.prev_issue_btn, self.next_issue_btn, self.play_btn, self.open_btn, self.edit_btn, self.save_btn, self.back_btn]:
            button_row.addWidget(button)
        left_layout.addLayout(button_row)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        left_layout.addWidget(self.log_output, 1)

        right_layout.addWidget(QLabel("问题片段"))
        self.video_widget = FfmpegVideoWidget()
        right_layout.addWidget(self.video_widget, 1)

        control_row = QHBoxLayout()
        self.video_play_btn = QPushButton("播放")
        self.video_pause_btn = QPushButton("暂停")
        self.video_back_btn = QPushButton("后退")
        self.video_forward_btn = QPushButton("前进")
        self.step_box = QComboBox()
        self.step_box.addItem("0.1s", 0.1)
        self.step_box.addItem("1s", 1.0)
        self.step_box.addItem("5s", 5.0)
        control_row.addWidget(self.video_play_btn)
        control_row.addWidget(self.video_pause_btn)
        control_row.addWidget(self.video_back_btn)
        control_row.addWidget(self.video_forward_btn)
        control_row.addWidget(QLabel("步长"))
        control_row.addWidget(self.step_box)
        right_layout.addLayout(control_row)

        self.player_label = QLabel("未选择片段")
        self.player_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.player_label.setWordWrap(True)
        right_layout.addWidget(self.player_label)

        self.browse_btn.clicked.connect(self.browse_output_path)
        self.refresh_btn.clicked.connect(self.refresh_runs)
        self.filter_field_box.currentIndexChanged.connect(self._refresh_filter_values)
        self.filter_value_box.currentIndexChanged.connect(self.apply_issue_filters)
        self.clear_filter_btn.clicked.connect(self.clear_filters)
        self.run_list.itemSelectionChanged.connect(self.on_run_selected)
        self.issue_table.itemSelectionChanged.connect(self.on_issue_selected)
        self.issue_table.itemDoubleClicked.connect(lambda _item: self.play_selected_issue())
        self.prev_issue_btn.clicked.connect(self.select_previous_issue)
        self.next_issue_btn.clicked.connect(self.select_next_issue)
        self.play_btn.clicked.connect(self.play_selected_issue)
        self.open_btn.clicked.connect(self.open_selected_issue_externally)
        self.edit_btn.clicked.connect(self.enable_editing)
        self.save_btn.clicked.connect(self.save_issue)
        self.video_play_btn.clicked.connect(self.play_or_resume_clip)
        self.video_pause_btn.clicked.connect(self.pause_clip)
        self.video_back_btn.clicked.connect(self.step_backward)
        self.video_forward_btn.clicked.connect(self.step_forward)
        self.step_box.currentIndexChanged.connect(self.on_step_changed)
        self.video_widget.status_changed.connect(self.on_video_status_changed)
        self.video_widget.busy_changed.connect(self.on_video_busy_changed)

        self.on_step_changed(0)
        self._set_edit_enabled(False)
        self._apply_panel_widths()

    def _fill_combo(self, combo: QComboBox, values: List[str], include_empty: bool = False) -> None:
        combo.clear()
        if include_empty:
            combo.addItem("", "")
        for value in values:
            combo.addItem(zh(value), value)

    @staticmethod
    def _combo_value(combo: QComboBox) -> str:
        return str(combo.currentData() or combo.currentText())

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _issue_value(self, issue: Dict[str, object], field_key: str) -> object:
        if field_key == "active_safety_result":
            return issue.get("takeover_result") or issue.get("road_test_result") or ""
        if field_key == "case_id" and self._issue_schema(issue) == CAMPUS_ROAD_MARKING_SCHEMA:
            return ""
        return issue.get(field_key, "")

    def _issue_schema(self, issue: Optional[Dict[str, object]]) -> str:
        if issue and issue.get('marking_schema') == 'active_safety':
            return 'active_safety'
        if issue and issue.get('marking_schema') == CAMPUS_ROAD_MARKING_SCHEMA:
            return CAMPUS_ROAD_MARKING_SCHEMA
        if self.current_run and self.current_run.get('test_function') == CAMPUS_ROAD_TEST_FUNCTION:
            return CAMPUS_ROAD_MARKING_SCHEMA
        return 'legacy'

    def _is_campus_road_issue(self, issue: Optional[Dict[str, object]]) -> bool:
        return self._issue_schema(issue) == CAMPUS_ROAD_MARKING_SCHEMA

    def _standard_problem_options(self) -> Dict[str, List[str]]:
        if self._is_campus_road_issue(self.current_issue):
            return CAMPUS_PROBLEM_OPTIONS
        return PROBLEM_OPTIONS

    def _apply_standard_combo_options(self, schema: str) -> None:
        if schema == CAMPUS_ROAD_MARKING_SCHEMA:
            road_types = CAMPUS_ROAD_TYPES
            scene_types = CAMPUS_SCENE_TYPES
            problem_options = CAMPUS_PROBLEM_OPTIONS
            target_types = CAMPUS_TARGET_TYPES
            ego_actions = CAMPUS_EGO_ACTIONS
        else:
            road_types = LEGACY_ROAD_TYPES
            scene_types = LEGACY_SCENE_TYPES
            problem_options = PROBLEM_OPTIONS
            target_types = LEGACY_TARGET_TYPES
            ego_actions = LEGACY_EGO_ACTIONS

        self.problem_tab.blockSignals(True)
        self._fill_combo(self.road_type, road_types)
        self._fill_combo(self.scene_type, scene_types)
        self._fill_combo(self.problem_tab, list(problem_options.keys()))
        self._fill_combo(self.target_type, target_types)
        self._fill_combo(self.ego_action, ego_actions)
        self.problem_tab.blockSignals(False)
        self._refresh_problem_types(self.problem_tab.currentIndex())

    def set_output_path(self, output_path: str) -> None:
        self.output_path.setText(output_path)
        self.playback_service.set_base_dir(Path(output_path))

    def browse_output_path(self) -> None:
        start_dir = self.output_path.text().strip() or str(Path.cwd())
        selected_dir = QFileDialog.getExistingDirectory(self, "选择 run 文件夹", start_dir)
        if not selected_dir:
            return
        self.set_output_path(selected_dir)
        self.refresh_runs()

    def append_log(self, message: str) -> None:
        self.log_output.append(message)

    def refresh_runs(self) -> None:
        base_dir = Path(self.output_path.text().strip())
        self.playback_service.set_base_dir(base_dir)
        self.run_list.clear()
        self.issue_table.setRowCount(0)
        self.current_run = None
        self.current_issue = None
        self.all_issues = []
        self.visible_issues = []
        runs = self.playback_service.list_runs()
        for run in runs:
            state_text = zh(run.get('state', ''))
            issue_count = run.get('issue_count', 0)
            test_function = run.get('test_function', '行车-外部路测试')
            display_name = f"{run.get('test_date', '-')} | {test_function} | {run.get('vehicle_model', '-')} | {run.get('vehicle_id', '-')} | {run.get('run_id', '-')} | {state_text} | 问题数={issue_count}"
            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, run)
            self.run_list.addItem(item)
        self.issue_count_label.setText('可见问题数：0')
        self.append_log(f"已从 {base_dir} 加载 {len(runs)} 个 run")
        if not runs:
            self.player_label.setText("所选文件夹中没有 run")
            self.video_widget.clear('未选择片段')

    def on_run_selected(self) -> None:
        item = self.run_list.currentItem()
        if item is None:
            return
        run = item.data(Qt.UserRole)
        self.current_run = run
        run_root = Path(str(run['run_root']))
        self.all_issues = self.playback_service.load_issues(run_root)
        self._refresh_filter_values()
        self.apply_issue_filters()
        self.append_log(f"已为 {run['run_id']} 加载 {len(self.all_issues)} 个 issue，测试功能：{run.get('test_function', '行车-外部路测试')}")

    def _refresh_filter_values(self) -> None:
        field_key = str(self.filter_field_box.currentData() or '')
        current_value = str(self.filter_value_box.currentData() or '')
        self.filter_value_box.blockSignals(True)
        self.filter_value_box.clear()
        self.filter_value_box.addItem('全部', '')
        values = []
        for issue in self.all_issues:
            raw = self._issue_value(issue, field_key)
            if raw is None:
                continue
            text = str(raw).strip()
            if not text:
                continue
            values.append(text)
        for value in sorted(set(values)):
            self.filter_value_box.addItem(zh(value), value)
        index = self.filter_value_box.findData(current_value)
        self.filter_value_box.setCurrentIndex(index if index >= 0 else 0)
        self.filter_value_box.blockSignals(False)

    def apply_issue_filters(self) -> None:
        if not self.current_run:
            self.visible_issues = []
            self.issue_table.setRowCount(0)
            self.issue_count_label.setText('可见问题数：0')
            return

        selected_issue_id = str(self.current_issue.get('issue_id')) if self.current_issue else None
        field_key = str(self.filter_field_box.currentData() or '')
        field_value = str(self.filter_value_box.currentData() or '')
        self.visible_issues = []
        for issue in self.all_issues:
            if field_value and str(self._issue_value(issue, field_key)) != field_value:
                continue
            self.visible_issues.append(issue)

        self._populate_issue_table(self.visible_issues)
        self.issue_count_label.setText(f'可见问题数：{len(self.visible_issues)}')
        if selected_issue_id:
            self._select_issue_by_id(selected_issue_id)

    def clear_filters(self) -> None:
        self.filter_field_box.setCurrentIndex(0)
        self._refresh_filter_values()
        self.filter_value_box.setCurrentIndex(0)
        self.apply_issue_filters()

    def _populate_issue_table(self, issues: List[Dict[str, object]]) -> None:
        self.issue_table.setSortingEnabled(False)
        self.issue_table.setRowCount(len(issues))
        for row, issue in enumerate(issues):
            lat = issue.get('latitude')
            lon = issue.get('longitude')
            latlon = '-'
            if lat is not None and lon is not None:
                latlon = f"{lat:.6f}, {lon:.6f}"
            values = {
                'seq_no': issue.get('seq_no', ''),
                'issue_time_text': issue.get('issue_time_text', ''),
                'latlon': latlon,
                'case_id': self._issue_value(issue, 'case_id'),
                'active_safety_function': issue.get('active_safety_function', ''),
                'active_safety_mode': issue.get('active_safety_mode', ''),
                'speed_kph': issue.get('speed_kph', ''),
                'active_safety_result': self._issue_value(issue, 'active_safety_result'),
                'road_type': zh(issue.get('road_type', '')),
                'scene_type': zh(issue.get('scene_type', '')),
                'problem_type': zh(issue.get('problem_type', '')),
                'target_type': zh(issue.get('target_type', '')),
                'ego_action': zh(issue.get('ego_action', '')),
                'comment': issue.get('comment', ''),
                'triage': zh(issue.get('triage', 'untriaged')),
                'triage_time': issue.get('triage_time', '') or '',
            }
            for col, (_title, key, _width) in enumerate(self.TABLE_COLUMNS):
                item = QTableWidgetItem(str(values[key]))
                item.setData(Qt.UserRole, str(issue.get('issue_id', '')))
                if key == 'seq_no':
                    item.setData(Qt.UserRole + 1, int(issue.get('seq_no', 0) or 0))
                self.issue_table.setItem(row, col, item)
        self.issue_table.setSortingEnabled(True)
        self.issue_table.sortItems(0, Qt.AscendingOrder)

    def on_issue_selected(self) -> None:
        row = self.issue_table.currentRow()
        if row < 0:
            self.current_issue = None
            self.current_clip_path = None
            return
        item = self.issue_table.item(row, 0)
        issue_id = item.data(Qt.UserRole) if item else None
        if not issue_id:
            return
        matched = next((issue for issue in self.visible_issues if str(issue.get('issue_id')) == str(issue_id)), None)
        if matched is None:
            return
        self.current_issue = dict(matched)
        self._load_issue_into_editor(self.current_issue)
        self.current_clip_path = self.playback_service.resolve_clip_path(Path(str(self.current_run['run_root'])), self.current_issue)
        if self.current_clip_path:
            self.player_label.setText(f"片段已就绪：{self.current_clip_path}")
        else:
            self.player_label.setText('没有可用片段')
            self.video_widget.clear('未选择片段')
        self._set_edit_enabled(False)

    def select_previous_issue(self) -> None:
        row = self.issue_table.currentRow()
        if row > 0:
            self.issue_table.selectRow(row - 1)

    def select_next_issue(self) -> None:
        row = self.issue_table.currentRow()
        if row < self.issue_table.rowCount() - 1:
            self.issue_table.selectRow(row + 1)

    def play_selected_issue(self) -> None:
        if not self.current_run or not self.current_issue:
            QMessageBox.information(self, '回放 / 编辑', '请先选择一个 issue。')
            return
        clip_path = self.playback_service.resolve_clip_path(Path(str(self.current_run['run_root'])), self.current_issue)
        self.current_clip_path = clip_path
        if clip_path is None:
            QMessageBox.information(self, '回放 / 编辑', '该 issue 没有片段路径。')
            return
        if not clip_path.exists():
            self.player_label.setText(f'缺少片段：{clip_path}')
            self.video_widget.clear('缺少片段文件')
            self.append_log(f'缺少片段文件：{clip_path}')
            QMessageBox.information(self, '回放 / 编辑', '这个 issue 暂时没有可播放的片段。')
            return
        self.append_log(f'正在加载片段：{clip_path}')
        self.video_widget.play(clip_path)

    def play_or_resume_clip(self) -> None:
        if self.current_clip_path is None:
            self.play_selected_issue()
            return
        self.video_widget.play()

    def pause_clip(self) -> None:
        self.video_widget.pause()

    def step_backward(self) -> None:
        self.video_widget.step_backward()

    def step_forward(self) -> None:
        self.video_widget.step_forward()

    def on_step_changed(self, index: int) -> None:
        step = float(self.step_box.itemData(index))
        self.video_widget.set_step_seconds(step)

    def open_selected_issue_externally(self) -> None:
        if self.current_clip_path is None or not self.current_clip_path.exists():
            QMessageBox.information(self, '回放 / 编辑', '请先选择一个带有有效片段的 issue。')
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.current_clip_path.resolve())))
        self.append_log(f'已使用外部播放器打开：{self.current_clip_path}')

    def enable_editing(self) -> None:
        if not self.current_issue:
            QMessageBox.information(self, '回放 / 编辑', '请先选择一个 issue。')
            return
        self._set_edit_enabled(True)
        self.append_log(f"已启用编辑：{self.current_issue.get('issue_id')}")

    def save_issue(self) -> None:
        if not self.current_run or not self.current_issue:
            return
        updates = {
            'road_type': self._combo_value(self.road_type),
            'scene_type': self._combo_value(self.scene_type),
            'problem_tab': self._combo_value(self.problem_tab),
            'problem_type': self._combo_value(self.problem_type),
            'target_type': self._combo_value(self.target_type),
            'ego_action': self._combo_value(self.ego_action),
            'case_id': self.case_id.text().strip(),
            'comment': self.comment.toPlainText().strip(),
        }
        if self.current_issue.get('marking_schema') == 'active_safety':
            active_mode = self._combo_value(self.active_safety_mode)
            is_field_test = active_mode == '场测'
            takeover_result = self._combo_value(self.takeover_result) if is_field_test else ''
            road_test_result = self._combo_value(self.road_test_result) if not is_field_test else ''
            updates.update({
                'marking_schema': 'active_safety',
                'active_safety_function': self._combo_value(self.active_safety_function),
                'active_safety_mode': active_mode,
                'speed_kph': self.speed_kph.text().strip() if is_field_test else '',
                'takeover_result': takeover_result,
                'road_test_result': road_test_result,
                'case_id': self.case_id.text().strip() if is_field_test else '',
                'problem_tab': 'Active safety',
                'problem_type': self._combo_value(self.active_safety_function),
                'ego_action': takeover_result or road_test_result,
            })
        elif self._is_campus_road_issue(self.current_issue):
            updates.update({
                'marking_schema': CAMPUS_ROAD_MARKING_SCHEMA,
                'case_id': '',
                'active_safety_function': '',
                'active_safety_mode': '',
                'speed_kph': '',
                'takeover_result': '',
                'road_test_result': '',
            })
        run_root = Path(str(self.current_run['run_root']))
        updated = self.playback_service.update_issue(run_root, str(self.current_issue['issue_id']), updates)
        self.append_log(f"已更新 issue：{updated['issue_id']}")
        self.current_issue = dict(updated)
        self.all_issues = self.playback_service.load_issues(run_root)
        self._refresh_filter_values()
        self.apply_issue_filters()
        self._select_issue_by_id(str(updated['issue_id']))
        self._set_edit_enabled(False)

    def on_video_status_changed(self, message: str) -> None:
        self.player_label.setText(message if not self.current_clip_path else f'{message} | {self.current_clip_path}')
        self.append_log(message)

    def on_video_busy_changed(self, busy: bool) -> None:
        self.video_play_btn.setEnabled(not busy)
        self.video_pause_btn.setEnabled(not busy)
        self.video_back_btn.setEnabled(not busy)
        self.video_forward_btn.setEnabled(not busy)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._apply_panel_widths()

    def _apply_panel_widths(self) -> None:
        margins = self.layout().contentsMargins()  # type: ignore[call-arg]
        spacing = self.layout().spacing()  # type: ignore[call-arg]
        available = max(0, self.width() - margins.left() - margins.right() - spacing)
        left_width = max(520, int(available * 0.4))
        right_width = max(760, available - left_width)
        self.left_panel.setFixedWidth(left_width)
        self.right_panel.setFixedWidth(right_width)

    def _refresh_problem_types(self, _index: int) -> None:
        current_value = self._combo_value(self.problem_type)
        problem_tab = self._combo_value(self.problem_tab)
        self._fill_combo(self.problem_type, self._standard_problem_options().get(problem_tab, []))
        self._set_combo_value(self.problem_type, current_value)

    def _load_issue_into_editor(self, issue: Dict[str, object]) -> None:
        self._apply_standard_combo_options(self._issue_schema(issue))
        self._set_combo_value(self.road_type, str(issue.get('road_type', '')))
        self._set_combo_value(self.scene_type, str(issue.get('scene_type', '')))
        tab_name = str(issue.get('problem_tab', ''))
        if tab_name:
            self._set_combo_value(self.problem_tab, tab_name)
        self._refresh_problem_types(self.problem_tab.currentIndex())
        self._set_combo_value(self.problem_type, str(issue.get('problem_type', '')))
        self._set_combo_value(self.target_type, str(issue.get('target_type', '')))
        self._set_combo_value(self.ego_action, str(issue.get('ego_action', '')))
        if self._is_campus_road_issue(issue):
            self.case_id.setText("")
        else:
            self.case_id.setText(str(issue.get('case_id', '')))
        self._set_combo_value(self.active_safety_function, str(issue.get('active_safety_function', '')))
        self._set_combo_value(self.active_safety_mode, str(issue.get('active_safety_mode', '')))
        self.speed_kph.setText(str(issue.get('speed_kph', '')))
        self._set_combo_value(self.takeover_result, str(issue.get('takeover_result', '')))
        self._set_combo_value(self.road_test_result, str(issue.get('road_test_result', '')))
        self.comment.setPlainText(str(issue.get('comment', '')))

    def _select_issue_by_id(self, issue_id: str) -> None:
        for row in range(self.issue_table.rowCount()):
            item = self.issue_table.item(row, 0)
            if item and str(item.data(Qt.UserRole)) == issue_id:
                self.issue_table.selectRow(row)
                break

    def _set_edit_enabled(self, enabled: bool) -> None:
        self.edit_mode = enabled
        is_active_safety = bool(
            self._issue_schema(self.current_issue) == 'active_safety'
        )
        is_campus_road = self._is_campus_road_issue(self.current_issue)
        standard_enabled = enabled and not is_active_safety
        active_enabled = enabled and is_active_safety

        for widget in [
            self.road_type,
            self.scene_type,
            self.problem_tab,
            self.problem_type,
            self.target_type,
            self.ego_action,
        ]:
            widget.setEnabled(standard_enabled)

        for widget in [
            self.active_safety_function,
            self.active_safety_mode,
            self.speed_kph,
            self.takeover_result,
            self.road_test_result,
        ]:
            widget.setEnabled(active_enabled)

        for widget in [
            self.comment,
        ]:
            widget.setEnabled(enabled)
        self.case_id.setEnabled(enabled and not is_campus_road)
        self.save_btn.setEnabled(enabled)
