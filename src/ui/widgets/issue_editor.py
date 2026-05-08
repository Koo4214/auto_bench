from __future__ import annotations

from typing import Dict, List, Optional

from PyQt5.QtCore import QObject, Qt, QStringListModel, pyqtSignal
from PyQt5.QtWidgets import (
    QButtonGroup,
    QCompleter,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.ui.i18n import zh
from src.ui.widgets.active_safety_case_ids import (
    ACTIVE_SAFETY_FUNCTIONS,
    load_active_safety_case_id_catalog,
)


PROBLEM_OPTIONS: Dict[str, List[str]] = {
    "Lateral": [
        "Lane edge / line pressure",
        "Weaving / snake",
        "Lane departure",
        "Bad split lane choice",
        "Bad intersection trajectory",
    ],
    "Longitudinal": [
        "Accel / brake jerk",
        "Rollback",
        "Following too near / far",
        "Brake too hard",
        "Insufficient braking",
        "Unexpected decel",
        "Bad speed limit handling",
        "No accel / slow accel",
        "Aggressive accel",
    ],
    "Lane change": [
        "Nav lane change missing",
        "Nav lane change late",
        "Nav lane change noisy",
        "Efficiency lane change missing",
        "Efficiency lane change late",
        "Efficiency lane change noisy",
        "Unsafe lane change",
        "Hesitant lane change",
        "Cannot find a gap",
    ],
    "Compliance": [
        "Solid line crossing",
        "Red light violation",
        "No waiting area",
    ],
    "Function": [
        "Function unavailable",
        "Function degraded",
    ],
    "No issue": [
        "Scene record",
        "Good case",
    ],
}

CAMPUS_ROAD_TEST_FUNCTION = "行车-园区测试"
CAMPUS_ROAD_MARKING_SCHEMA = "campus_road_test"

CAMPUS_ROAD_TYPES: List[str] = [
    "园区地面",
    "园区地库",
]

CAMPUS_SCENE_TYPES: List[str] = [
    "直道",
    "弯道",
    "左转",
    "右转",
    "闸机",
    "掉头",
    "进园区",
    "出园区",
    "泊入",
    "泊出",
]

CAMPUS_PROBLEM_OPTIONS: Dict[str, List[str]] = {
    "安全问题": [
        "撞路沿/障碍物",
        "不减速/制动不足",
        "跟/停距离太近",
        "逆向目标避让不足",
        "路口挤压旁车",
        "危险变道/绕行",
    ],
    "舒适问题": [
        "制动力过大",
        "加减速顿挫",
        "异常减速",
        "溜车",
        "摆动/蛇形",
        "路口路径不合理",
        "预减速不足",
    ],
    "效率问题": [
        "跟/停距离远",
        "不加速/加速慢",
        "未及时变道/绕行",
        "行泊切换位置不合理",
    ],
    "合规问题": [
        "进逆向车道",
        "不居中/贴边",
        "压线",
        "不按导流/规定车道行驶",
        "不礼让行人",
    ],
    "导航问题": [
        "路口通行未跟导航",
    ],
    "其他": [
        "激活升级失败/异常降级",
        "转向灯问题",
        "误/错触发提醒",
        "漏触发提醒",
        "行泊切换失败",
        "车位激活失败",
    ],
    "goodcase": [
        "衔接成功",
        "闸机通行成功",
        "泊入成功",
        "泊出成功",
        "场景记录",
    ],
}

CAMPUS_TARGET_TYPES: List[str] = [
    "小汽车",
    "VRU",
    "障碍物",
    "其他",
    "无",
]

CAMPUS_EGO_ACTIONS: List[str] = [
    "安全接管",
    "效率接管",
    "合规接管",
    "体验接管",
    "导航接管",
    "无接管",
]


class OptionButtonGroup(QWidget):
    selection_changed = pyqtSignal(str)

    def __init__(self, title: str, options: List[str], columns: int = 3, button_height: int = 28) -> None:
        super().__init__()
        self._buttons: List[QPushButton] = []
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        box = QGroupBox(title)
        box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        box.setStyleSheet("QGroupBox { font-weight: 600; margin-top: 6px; } QGroupBox::title { subcontrol-origin: margin; left: 8px; }")
        box_layout = QGridLayout(box)
        box_layout.setContentsMargins(8, 12, 8, 8)
        box_layout.setHorizontalSpacing(6)
        box_layout.setVerticalSpacing(6)

        for index, option in enumerate(options):
            button = QPushButton(zh(option))
            button.setProperty('raw_value', option)
            button.setCheckable(True)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            button.setMinimumHeight(button_height)
            button.setStyleSheet(
                "QPushButton { padding: 4px 8px; border: 1px solid #666; border-radius: 6px; }"
                "QPushButton:checked { background: #1f6feb; color: white; border-color: #1f6feb; }"
            )
            row = index // columns
            col = index % columns
            box_layout.addWidget(button, row, col)
            self._button_group.addButton(button, index)
            self._buttons.append(button)

        self._button_group.buttonClicked[int].connect(
            lambda _button_id: self.selection_changed.emit(self.current_text())
        )
        layout.addWidget(box)
        if self._buttons:
            self._buttons[0].setChecked(True)
        height = box.sizeHint().height()
        box.setFixedHeight(height)
        self.setFixedHeight(height)

    def current_text(self) -> str:
        button = self._button_group.checkedButton()
        if not button:
            return ""
        return str(button.property('raw_value') or '')

    def set_current_text(self, text: str) -> None:
        for button in self._buttons:
            if str(button.property('raw_value') or '') == text:
                button.setChecked(True)
                return


class ProblemSelector(QWidget):
    def __init__(
        self,
        options_by_tab: Optional[Dict[str, List[str]]] = None,
        group_columns: int = 2,
        button_height: int = 28,
    ) -> None:
        super().__init__()
        self._groups: Dict[str, OptionButtonGroup] = {}
        self._tab_keys: List[str] = []
        options_by_tab = options_by_tab or PROBLEM_OPTIONS

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        box = QGroupBox("问题类型")
        box.setStyleSheet("QGroupBox { font-weight: 600; margin-top: 6px; } QGroupBox::title { subcontrol-origin: margin; left: 8px; }")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(8, 12, 8, 8)
        box_layout.setSpacing(6)

        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        for tab_name, options in options_by_tab.items():
            group = OptionButtonGroup(zh(tab_name), options, columns=group_columns, button_height=button_height)
            self._groups[tab_name] = group
            self._tab_keys.append(tab_name)
            self.tab_widget.addTab(group, zh(tab_name))
        box_layout.addWidget(self.tab_widget)
        layout.addWidget(box)

    def current_problem_tab(self) -> str:
        index = self.tab_widget.currentIndex()
        if index < 0 or index >= len(self._tab_keys):
            return ""
        return self._tab_keys[index]

    def current_problem_type(self) -> str:
        tab_name = self.current_problem_tab()
        if not tab_name:
            return ""
        return self._groups[tab_name].current_text()

    def set_problem(self, tab_name: str, problem_type: Optional[str] = None) -> None:
        for index, raw_name in enumerate(self._tab_keys):
            if raw_name == tab_name:
                self.tab_widget.setCurrentIndex(index)
                if problem_type:
                    self._groups[tab_name].set_current_text(problem_type)
                return


class LegacyIssueEditorPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignTop)

        title = QLabel("问题打点")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        layout.addWidget(title)

        self.road_type = OptionButtonGroup(
            "道路类型",
            [
                "Urban main road",
                "Urban expressway",
                "Urban narrow road",
                "Campus ground",
                "Campus garage",
            ],
            columns=3,
            button_height=28,
        )
        layout.addWidget(self.road_type)

        self.scene_type = OptionButtonGroup(
            "场景类型",
            [
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
            ],
            columns=3,
            button_height=28,
        )
        layout.addWidget(self.scene_type)

        self.problem_selector = ProblemSelector()
        layout.addWidget(self.problem_selector)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)
        self.target_type = OptionButtonGroup(
            "目标类型",
            [
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
            ],
            columns=2,
            button_height=28,
        )
        bottom_row.addWidget(self.target_type, 1)

        self.ego_action = OptionButtonGroup(
            "本车操作",
            [
                "Safety takeover",
                "Experience takeover",
                "No action",
            ],
            columns=1,
            button_height=28,
        )
        bottom_row.addWidget(self.ego_action, 1)
        layout.addLayout(bottom_row)

        case_box = QGroupBox("Case ID")
        case_box.setStyleSheet("QGroupBox { font-weight: 600; margin-top: 6px; } QGroupBox::title { subcontrol-origin: margin; left: 8px; }")
        case_layout = QVBoxLayout(case_box)
        case_layout.setContentsMargins(8, 12, 8, 8)
        self.case_id = QLineEdit()
        self.case_id.setPlaceholderText("可选，用于泊车/场地/主动安全用例绑定")
        case_layout.addWidget(self.case_id)
        layout.addWidget(case_box)

        comment_box = QGroupBox("备注")
        comment_box.setStyleSheet("QGroupBox { font-weight: 600; margin-top: 6px; } QGroupBox::title { subcontrol-origin: margin; left: 8px; }")
        comment_layout = QVBoxLayout(comment_box)
        comment_layout.setContentsMargins(8, 12, 8, 8)
        self.comment = QTextEdit()
        self.comment.setPlaceholderText("可选备注")
        self.comment.setFixedHeight(36)
        comment_layout.addWidget(self.comment)
        layout.addWidget(comment_box)

        footer = QHBoxLayout()
        self.issue_count_label = QLabel("问题数量：0")
        footer.addWidget(self.issue_count_label)
        footer.addStretch(1)
        layout.addLayout(footer)

        self.add_issue_btn = QPushButton("创建打点")
        self.add_issue_btn.setMinimumHeight(34)
        self.add_issue_btn.setStyleSheet(
            "QPushButton { background: #d95550; color: white; border: none; border-radius: 6px; font-weight: 600; }"
            "QPushButton:pressed { background: #bf4b47; }"
        )
        layout.addWidget(self.add_issue_btn)

    def get_issue_payload(self) -> Dict[str, str]:
        return {
            "road_type": self.road_type.current_text(),
            "scene_type": self.scene_type.current_text(),
            "problem_tab": self.problem_selector.current_problem_tab(),
            "problem_type": self.problem_selector.current_problem_type(),
            "target_type": self.target_type.current_text(),
            "ego_action": self.ego_action.current_text(),
            "case_id": self.case_id.text().strip(),
            "comment": self.comment.toPlainText().strip(),
        }

    def set_issue_count(self, count: int) -> None:
        self.issue_count_label.setText(f"问题数量：{count}")

    def clear_comment(self) -> None:
        self.comment.clear()


class CampusRoadIssueEditorPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignTop)

        title = QLabel("园区路试打点")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        layout.addWidget(title)

        self.road_type = OptionButtonGroup(
            "道路类型",
            CAMPUS_ROAD_TYPES,
            columns=2,
            button_height=24,
        )
        layout.addWidget(self.road_type)

        self.scene_type = OptionButtonGroup(
            "场景类型",
            CAMPUS_SCENE_TYPES,
            columns=5,
            button_height=24,
        )
        layout.addWidget(self.scene_type)

        self.problem_selector = ProblemSelector(
            CAMPUS_PROBLEM_OPTIONS,
            group_columns=3,
            button_height=24,
        )
        layout.addWidget(self.problem_selector)

        self.target_type = OptionButtonGroup(
            "目标类型",
            CAMPUS_TARGET_TYPES,
            columns=5,
            button_height=24,
        )
        layout.addWidget(self.target_type)

        self.ego_action = OptionButtonGroup(
            "本车操作",
            CAMPUS_EGO_ACTIONS,
            columns=3,
            button_height=24,
        )
        layout.addWidget(self.ego_action)

        comment_box = QGroupBox("备注")
        comment_box.setStyleSheet("QGroupBox { font-weight: 600; margin-top: 6px; } QGroupBox::title { subcontrol-origin: margin; left: 8px; }")
        comment_layout = QVBoxLayout(comment_box)
        comment_layout.setContentsMargins(8, 12, 8, 6)
        self.comment = QTextEdit()
        self.comment.setPlaceholderText("可选备注")
        self.comment.setFixedHeight(34)
        comment_layout.addWidget(self.comment)
        layout.addWidget(comment_box)

        footer = QHBoxLayout()
        self.issue_count_label = QLabel("问题数量：0")
        footer.addWidget(self.issue_count_label)
        footer.addStretch(1)
        layout.addLayout(footer)

        self.add_issue_btn = QPushButton("创建打点")
        self.add_issue_btn.setMinimumHeight(34)
        self.add_issue_btn.setStyleSheet(
            "QPushButton { background: #d95550; color: white; border: none; border-radius: 6px; font-weight: 600; }"
            "QPushButton:pressed { background: #bf4b47; }"
        )
        layout.addWidget(self.add_issue_btn)
        layout.addStretch(1)

    def get_issue_payload(self) -> Dict[str, str]:
        return {
            "road_type": self.road_type.current_text(),
            "scene_type": self.scene_type.current_text(),
            "problem_tab": self.problem_selector.current_problem_tab(),
            "problem_type": self.problem_selector.current_problem_type(),
            "target_type": self.target_type.current_text(),
            "ego_action": self.ego_action.current_text(),
            "case_id": "",
            "comment": self.comment.toPlainText().strip(),
            "marking_schema": CAMPUS_ROAD_MARKING_SCHEMA,
        }

    def set_issue_count(self, count: int) -> None:
        self.issue_count_label.setText(f"问题数量：{count}")

    def clear_comment(self) -> None:
        self.comment.clear()


class ActiveSafetyIssueEditorPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._case_catalog = load_active_safety_case_id_catalog()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("主动安全打点")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        title.setFixedHeight(title.sizeHint().height())
        layout.addWidget(title)

        self.function_group = OptionButtonGroup(
            "功能",
            list(ACTIVE_SAFETY_FUNCTIONS),
            columns=4,
            button_height=28,
        )
        self.function_group.selection_changed.connect(self._refresh_case_id_options)
        layout.addWidget(self.function_group)

        mode_box = QGroupBox("场测 / 路试")
        mode_box.setStyleSheet("QGroupBox { font-weight: 600; margin-top: 6px; } QGroupBox::title { subcontrol-origin: margin; left: 8px; }")
        mode_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        mode_layout = QVBoxLayout(mode_box)
        mode_layout.setContentsMargins(8, 12, 8, 6)
        mode_layout.setSpacing(4)

        self.mode_tabs = QTabWidget()
        self.mode_tabs.setDocumentMode(True)
        self.mode_tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.mode_tabs.addTab(self._build_field_test_tab(), "场测")
        self.mode_tabs.addTab(self._build_road_test_tab(), "路试")
        mode_layout.addWidget(self.mode_tabs)
        self.mode_tabs.setFixedHeight(self.mode_tabs.sizeHint().height())
        mode_box.setFixedHeight(mode_box.sizeHint().height())
        layout.addWidget(mode_box)

        comment_box = QGroupBox("备注")
        comment_box.setStyleSheet("QGroupBox { font-weight: 600; margin-top: 6px; } QGroupBox::title { subcontrol-origin: margin; left: 8px; }")
        comment_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        comment_layout = QVBoxLayout(comment_box)
        comment_layout.setContentsMargins(8, 12, 8, 6)
        comment_layout.setSpacing(0)
        self.comment = QTextEdit()
        self.comment.setPlaceholderText("可选备注")
        self.comment.setFixedHeight(self.comment.fontMetrics().lineSpacing() * 5 + 18)
        comment_layout.addWidget(self.comment)
        comment_box.setFixedHeight(comment_box.sizeHint().height())
        layout.addWidget(comment_box)

        footer = QHBoxLayout()
        self.case_id_counts: Dict[str, int] = {}
        self.issue_count_label = QLabel("当前 case ID 测试次数：0")
        self.issue_count_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.issue_count_label.setFixedHeight(self.issue_count_label.sizeHint().height())
        footer.addWidget(self.issue_count_label)
        footer.addStretch(1)
        layout.addLayout(footer)

        self.add_issue_btn = QPushButton("创建打点")
        self.add_issue_btn.setMinimumHeight(34)
        self.add_issue_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.add_issue_btn.setStyleSheet(
            "QPushButton { background: #d95550; color: white; border: none; border-radius: 6px; font-weight: 600; }"
            "QPushButton:pressed { background: #bf4b47; }"
        )
        layout.addWidget(self.add_issue_btn)
        layout.addStretch(1)

        self._refresh_case_id_options()

    def _build_field_test_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignTop)

        self.case_id = QLineEdit()
        self.case_id.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.case_id.setPlaceholderText("输入 AEB/RAEB 等搜索 case ID")
        self.case_id_model = QStringListModel(self)
        completer = QCompleter(self.case_id_model, self.case_id)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.case_id.setCompleter(completer)
        self.case_id_completer = completer
        self.case_id.textEdited.connect(self._refresh_case_id_options)
        self.case_id.textChanged.connect(self._refresh_case_id_count_label)
        layout.addWidget(QLabel("case ID"))
        layout.addWidget(self.case_id)

        speed_row = QHBoxLayout()
        self.speed_kph = QLineEdit()
        self.speed_kph.setPlaceholderText("速度")
        speed_row.addWidget(QLabel("速度"))
        speed_row.addWidget(self.speed_kph, 1)
        speed_row.addWidget(QLabel("kph"))
        layout.addLayout(speed_row)

        self.takeover_result = OptionButtonGroup(
            "测试结果",
            ["pass", "fail"],
            columns=2,
            button_height=28,
        )
        layout.addWidget(self.takeover_result)
        return tab

    def _build_road_test_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignTop)
        self.road_test_result = OptionButtonGroup(
            "结果",
            ["正触发", "误触发", "漏触发"],
            columns=1,
            button_height=28,
        )
        layout.addWidget(self.road_test_result)
        return tab

    def _refresh_case_id_options(self, _value: str = "") -> None:
        text = self.case_id.text().strip() if hasattr(self, "case_id") else ""
        function_name = self.function_group.current_text()
        options = self._case_catalog.search(function_name, text, limit=200)
        self.case_id_model.setStringList(options)
        if text and options:
            self.case_id_completer.complete()
        self._refresh_case_id_count_label()

    def _refresh_case_id_count_label(self) -> None:
        case_id = self.case_id.text().strip()
        count = self.case_id_counts.get(case_id, 0) if case_id else 0
        self.issue_count_label.setText(f"当前 case ID 测试次数：{count}")

    def get_issue_payload(self) -> Dict[str, str]:
        function_name = self.function_group.current_text()
        is_field_test = self.mode_tabs.currentIndex() == 0
        mode = "场测" if is_field_test else "路试"
        case_id = self.case_id.text().strip() if is_field_test else ""
        speed_kph = self.speed_kph.text().strip() if is_field_test else ""
        takeover_result = self.takeover_result.current_text() if is_field_test else ""
        road_test_result = self.road_test_result.current_text() if not is_field_test else ""
        result_text = takeover_result or road_test_result
        return {
            "road_type": "",
            "scene_type": "",
            "problem_tab": "Active safety",
            "problem_type": function_name,
            "target_type": "",
            "ego_action": result_text,
            "case_id": case_id,
            "comment": self.comment.toPlainText().strip(),
            "marking_schema": "active_safety",
            "active_safety_function": function_name,
            "active_safety_mode": mode,
            "speed_kph": speed_kph,
            "takeover_result": takeover_result,
            "road_test_result": road_test_result,
        }

    def set_issue_count(self, count: int) -> None:
        self._refresh_case_id_count_label()

    def set_case_id_counts(self, counts: Dict[str, int]) -> None:
        self.case_id_counts = counts
        self._refresh_case_id_count_label()

    def clear_comment(self) -> None:
        self.comment.clear()


class _IssueButtonProxy(QObject):
    clicked = pyqtSignal()


class CurrentPageStack(QStackedWidget):
    def sizeHint(self):  # type: ignore[override]
        current = self.currentWidget()
        return current.sizeHint() if current else super().sizeHint()

    def minimumSizeHint(self):  # type: ignore[override]
        current = self.currentWidget()
        return current.minimumSizeHint() if current else super().minimumSizeHint()


class IssueEditorWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.add_issue_btn = _IssueButtonProxy(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = CurrentPageStack()
        self.legacy_panel = LegacyIssueEditorPanel()
        self.campus_road_panel = CampusRoadIssueEditorPanel()
        self.active_safety_panel = ActiveSafetyIssueEditorPanel()
        self.stack.addWidget(self.legacy_panel)
        self.stack.addWidget(self.campus_road_panel)
        self.stack.addWidget(self.active_safety_panel)
        layout.addWidget(self.stack)

        self.legacy_panel.add_issue_btn.clicked.connect(lambda: self.add_issue_btn.clicked.emit())
        self.campus_road_panel.add_issue_btn.clicked.connect(lambda: self.add_issue_btn.clicked.emit())
        self.active_safety_panel.add_issue_btn.clicked.connect(lambda: self.add_issue_btn.clicked.emit())

    def set_test_function(self, test_function: str) -> None:
        if test_function == "主动安全测试":
            self.stack.setCurrentWidget(self.active_safety_panel)
        elif test_function == CAMPUS_ROAD_TEST_FUNCTION:
            self.stack.setCurrentWidget(self.campus_road_panel)
        else:
            self.stack.setCurrentWidget(self.legacy_panel)
        self.stack.updateGeometry()
        self.updateGeometry()

    def get_issue_payload(self) -> Dict[str, str]:
        panel = self.stack.currentWidget()
        if panel is self.active_safety_panel:
            return self.active_safety_panel.get_issue_payload()
        if panel is self.campus_road_panel:
            return self.campus_road_panel.get_issue_payload()
        return self.legacy_panel.get_issue_payload()

    def set_issue_count(self, count: int) -> None:
        self.legacy_panel.set_issue_count(count)
        self.campus_road_panel.set_issue_count(count)
        self.active_safety_panel.set_issue_count(count)

    def set_case_id_counts(self, counts: Dict[str, int]) -> None:
        self.active_safety_panel.set_case_id_counts(counts)

    def clear_comment(self) -> None:
        panel = self.stack.currentWidget()
        if panel is self.active_safety_panel:
            self.active_safety_panel.clear_comment()
        elif panel is self.campus_road_panel:
            self.campus_road_panel.clear_comment()
        else:
            self.legacy_panel.clear_comment()
