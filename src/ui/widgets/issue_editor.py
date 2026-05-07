from __future__ import annotations

from typing import Dict, List, Optional

from PyQt5.QtWidgets import (
    QButtonGroup,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.ui.i18n import zh


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


class OptionButtonGroup(QWidget):
    def __init__(self, title: str, options: List[str], columns: int = 3, button_height: int = 28) -> None:
        super().__init__()
        self._buttons: List[QPushButton] = []
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        box = QGroupBox(title)
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

        layout.addWidget(box)
        if self._buttons:
            self._buttons[0].setChecked(True)

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
    def __init__(self) -> None:
        super().__init__()
        self._groups: Dict[str, OptionButtonGroup] = {}
        self._tab_keys: List[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        box = QGroupBox("问题类型")
        box.setStyleSheet("QGroupBox { font-weight: 600; margin-top: 6px; } QGroupBox::title { subcontrol-origin: margin; left: 8px; }")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(8, 12, 8, 8)
        box_layout.setSpacing(6)

        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        for tab_name, options in PROBLEM_OPTIONS.items():
            group = OptionButtonGroup(zh(tab_name), options, columns=2, button_height=28)
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
        return self._groups[self.current_problem_tab()].current_text()

    def set_problem(self, tab_name: str, problem_type: Optional[str] = None) -> None:
        for index, raw_name in enumerate(self._tab_keys):
            if raw_name == tab_name:
                self.tab_widget.setCurrentIndex(index)
                if problem_type:
                    self._groups[tab_name].set_current_text(problem_type)
                return


class IssueEditorWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

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
