from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PyQt5.QtWidgets import QWidget


class SteeringWheelWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.current_angle: Optional[float] = None
        self.setMinimumHeight(132)

    def clear(self) -> None:
        self.current_angle = None
        self.update()

    def add_sample(self, _timestamp: float, value: Optional[float]) -> None:
        if value is None:
            return
        self.current_angle = float(value)
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        outer = self.rect().adjusted(6, 6, -6, -6)
        painter.fillRect(self.rect(), QColor("#0c1017"))
        painter.setPen(QColor("#2b3340"))
        painter.drawRect(outer)

        painter.setPen(QColor("#edf2fa"))
        painter.drawText(
            outer.adjusted(8, 0, -8, 0),
            Qt.AlignTop | Qt.AlignLeft,
            "方向盘角度",
        )

        badge_diameter = min(outer.width(), outer.height()) * 0.24
        badge_diameter = max(46.0, min(62.0, badge_diameter))
        badge_rect = QRectF(
            outer.right() - badge_diameter - 10.0,
            outer.top() + 8.0,
            badge_diameter,
            badge_diameter,
        )

        wheel_rect = QRectF(
            outer.left() + 14.0,
            outer.top() + 24.0,
            outer.width() - badge_diameter - 28.0,
            outer.height() - 34.0,
        )
        size = max(54.0, min(wheel_rect.width(), wheel_rect.height()) - 4.0)
        wheel_rect = QRectF(
            wheel_rect.center().x() - size / 2.0,
            wheel_rect.center().y() - size / 2.0,
            size,
            size,
        )

        self._draw_wheel(painter, wheel_rect, self.current_angle or 0.0)
        self._draw_badge(painter, badge_rect, self.current_angle)

        if self.current_angle is None:
            painter.setPen(QColor("#9aa5b5"))
            painter.drawText(wheel_rect, Qt.AlignCenter, "等待数据")

    def _draw_wheel(self, painter: QPainter, wheel_rect: QRectF, angle_deg: float) -> None:
        center = wheel_rect.center()
        radius = wheel_rect.width() / 2.0

        painter.save()
        painter.translate(center)
        # steering_angle_deg already includes the calibration-page inversion setting.
        # Positive values should render as left turn on screen.
        painter.rotate(-angle_deg)

        rim_rect = QRectF(-radius, -radius, radius * 2.0, radius * 2.0)
        rim_width = max(12.0, radius * 0.22)

        rim_grad = QRadialGradient(QPointF(0.0, 0.0), radius)
        rim_grad.setColorAt(0.0, QColor("#4a5362"))
        rim_grad.setColorAt(0.45, QColor("#2a313d"))
        rim_grad.setColorAt(1.0, QColor("#10151d"))
        painter.setPen(QPen(rim_grad, rim_width, Qt.SolidLine, Qt.RoundCap))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(rim_rect)

        outer_highlight_pen = QPen(QColor("#6d7687"), max(2.4, radius * 0.03), Qt.SolidLine, Qt.RoundCap)
        painter.setPen(outer_highlight_pen)
        painter.drawEllipse(rim_rect.adjusted(radius * 0.02, radius * 0.02, -radius * 0.02, -radius * 0.02))

        shadow_pen = QPen(QColor("#161b24"), max(3.0, radius * 0.04), Qt.SolidLine, Qt.RoundCap)
        painter.setPen(shadow_pen)
        painter.drawEllipse(rim_rect.adjusted(radius * 0.16, radius * 0.16, -radius * 0.16, -radius * 0.16))

        inner_ring_pen = QPen(QColor("#8993a5"), max(2.0, radius * 0.028), Qt.SolidLine, Qt.RoundCap)
        painter.setPen(inner_ring_pen)
        painter.drawEllipse(rim_rect.adjusted(radius * 0.11, radius * 0.11, -radius * 0.11, -radius * 0.11))

        top_mark_pen = QPen(QColor("#f4f7fb"), max(2.0, radius * 0.03), Qt.SolidLine, Qt.RoundCap)
        painter.setPen(top_mark_pen)
        painter.drawLine(QPointF(0.0, -radius * 0.9), QPointF(0.0, -radius * 0.73))

        spoke_grad = QLinearGradient(QPointF(0.0, -radius * 0.2), QPointF(0.0, radius * 0.55))
        spoke_grad.setColorAt(0.0, QColor("#4d5667"))
        spoke_grad.setColorAt(1.0, QColor("#1f2630"))
        spoke_pen = QPen(spoke_grad, max(8.0, radius * 0.12), Qt.SolidLine, Qt.RoundCap)
        painter.setPen(spoke_pen)
        painter.drawLine(QPointF(-radius * 0.55, -radius * 0.02), QPointF(-radius * 0.18, radius * 0.22))
        painter.drawLine(QPointF(radius * 0.55, -radius * 0.02), QPointF(radius * 0.18, radius * 0.22))
        painter.drawLine(QPointF(0.0, radius * 0.56), QPointF(0.0, radius * 0.2))

        self._draw_control_pod(painter, QPointF(-radius * 0.46, 0.02 * radius), radius, left_side=True)
        self._draw_control_pod(painter, QPointF(radius * 0.46, 0.02 * radius), radius, left_side=False)

        hub_rect = QRectF(-radius * 0.36, -radius * 0.03, radius * 0.72, radius * 0.63)
        hub_grad = QLinearGradient(hub_rect.topLeft(), hub_rect.bottomLeft())
        hub_grad.setColorAt(0.0, QColor("#5f6878"))
        hub_grad.setColorAt(0.08, QColor("#3a4352"))
        hub_grad.setColorAt(1.0, QColor("#202734"))
        painter.setPen(QPen(QColor("#7f8a9c"), 1.2))
        painter.setBrush(hub_grad)
        painter.drawRoundedRect(hub_rect, radius * 0.12, radius * 0.12)

        emblem_pen = QPen(QColor("#eef3fb"), max(2.0, radius * 0.055), Qt.SolidLine, Qt.RoundCap)
        painter.setPen(emblem_pen)
        self._draw_center_mark(painter, radius * 0.18)
        painter.setPen(QColor("#97a1b2"))
        brand_font = QFont(painter.font())
        brand_font.setPointSizeF(max(4.5, radius * 0.07))
        painter.setFont(brand_font)
        painter.drawText(
            QRectF(-radius * 0.22, radius * 0.18, radius * 0.44, radius * 0.12),
            Qt.AlignCenter,
            "AIRBAG",
        )
        painter.restore()

    def _draw_control_pod(self, painter: QPainter, center: QPointF, radius: float, left_side: bool) -> None:
        width = radius * 0.42
        height = radius * 0.18
        rect = QRectF(center.x() - width / 2.0, center.y() - height / 2.0, width, height)
        pod_grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        pod_grad.setColorAt(0.0, QColor("#6a7383"))
        pod_grad.setColorAt(1.0, QColor("#303846"))
        painter.setPen(QPen(QColor("#8a93a4"), 1.0))
        painter.setBrush(pod_grad)
        painter.drawRoundedRect(rect, radius * 0.05, radius * 0.05)

        painter.setPen(QPen(QColor("#d7dce6"), max(1.0, radius * 0.014), Qt.SolidLine, Qt.RoundCap))
        x1 = rect.left() + width * 0.22
        x2 = rect.center().x()
        x3 = rect.right() - width * 0.22
        y = rect.center().y()
        painter.drawLine(QPointF(x1 - radius * 0.03, y), QPointF(x1 + radius * 0.03, y))
        painter.drawLine(QPointF(x2, y - radius * 0.03), QPointF(x2, y + radius * 0.03))
        painter.drawLine(QPointF(x3 - radius * 0.025, y - radius * 0.02), QPointF(x3 + radius * 0.025, y + radius * 0.02))
        if left_side:
            painter.drawLine(QPointF(rect.left() + width * 0.1, y), QPointF(rect.left() + width * 0.16, y - radius * 0.02))
            painter.drawLine(QPointF(rect.left() + width * 0.1, y), QPointF(rect.left() + width * 0.16, y + radius * 0.02))
        else:
            painter.drawLine(QPointF(rect.right() - width * 0.1, y), QPointF(rect.right() - width * 0.16, y - radius * 0.02))
            painter.drawLine(QPointF(rect.right() - width * 0.1, y), QPointF(rect.right() - width * 0.16, y + radius * 0.02))

    def _draw_center_mark(self, painter: QPainter, size: float) -> None:
        path = QPainterPath()
        path.moveTo(-size, -size * 0.9)
        path.lineTo(-size * 0.18, -size * 0.12)
        path.lineTo(-size, size * 0.92)
        path.moveTo(size, -size * 0.9)
        path.lineTo(size * 0.18, -size * 0.12)
        path.lineTo(size, size * 0.92)
        painter.drawPath(path)

    def _draw_badge(self, painter: QPainter, rect: QRectF, angle: Optional[float]) -> None:
        painter.save()
        painter.setPen(QPen(QColor("#ff6d53"), 2.0))
        badge_grad = QRadialGradient(rect.center(), rect.width() * 0.6)
        badge_grad.setColorAt(0.0, QColor("#2a3445"))
        badge_grad.setColorAt(1.0, QColor("#111821"))
        painter.setBrush(badge_grad)
        painter.drawEllipse(rect)

        painter.setPen(QColor("#ffffff"))
        value_font = QFont(painter.font())
        value_font.setBold(True)
        value_font.setPointSize(max(8, int(rect.height() * 0.21)))
        painter.setFont(value_font)
        value_text = "--" if angle is None else f"{angle:+.1f}°"
        painter.drawText(
            rect.adjusted(0, rect.height() * 0.1, 0, -rect.height() * 0.35),
            Qt.AlignHCenter | Qt.AlignVCenter,
            value_text,
        )

        label_font = QFont(painter.font())
        label_font.setBold(True)
        label_font.setPointSize(max(7, int(rect.height() * 0.15)))
        painter.setFont(label_font)
        painter.drawText(
            rect.adjusted(0, rect.height() * 0.42, 0, -rect.height() * 0.08),
            Qt.AlignHCenter | Qt.AlignVCenter,
            "转角",
        )
        painter.restore()

