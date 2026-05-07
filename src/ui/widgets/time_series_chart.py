from __future__ import annotations

from collections import deque
from typing import Deque, Optional, Tuple

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QWidget


class TimeSeriesChart(QWidget):
    def __init__(
        self,
        title: str,
        color: str,
        y_unit: str = "",
        window_seconds: float = 6.0,
        baseline_value: Optional[float] = None,
        symmetric_baseline: bool = False,
        decimals: int = 2,
    ) -> None:
        super().__init__()
        self.title = title
        self.y_unit = y_unit
        self.window_seconds = window_seconds
        self.baseline_value = baseline_value
        self.symmetric_baseline = symmetric_baseline
        self.decimals = decimals
        self.samples: Deque[Tuple[float, float]] = deque(maxlen=400)
        self.line_color = QColor(color)
        self.setMinimumHeight(140)

    def clear(self) -> None:
        self.samples.clear()
        self.update()

    def add_sample(self, timestamp: float, value: Optional[float]) -> None:
        if value is None:
            return
        self.samples.append((timestamp, float(value)))
        self._trim(timestamp)
        self.update()

    def _trim(self, latest_timestamp: float) -> None:
        threshold = latest_timestamp - self.window_seconds
        while self.samples and self.samples[0][0] < threshold:
            self.samples.popleft()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        outer = self.rect().adjusted(6, 6, -6, -6)

        background = QLinearGradient(0.0, outer.top(), 0.0, outer.bottom())
        background.setColorAt(0.0, QColor("#121924"))
        background.setColorAt(1.0, QColor("#0b1017"))
        painter.fillRect(self.rect(), QColor("#0a0f16"))
        painter.fillRect(outer, background)
        painter.setPen(QColor("#2d3643"))
        painter.drawRect(outer)

        self._draw_header(painter, outer)

        plot_rect = outer.adjusted(44, 32, -12, -22)
        painter.setPen(QColor("#354051"))
        painter.drawLine(plot_rect.left(), plot_rect.top(), plot_rect.left(), plot_rect.bottom())
        painter.drawLine(plot_rect.left(), plot_rect.bottom(), plot_rect.right(), plot_rect.bottom())

        if len(self.samples) < 2:
            painter.setPen(QColor("#7d8797"))
            painter.drawText(plot_rect, Qt.AlignCenter, "\u7b49\u5f85\u6570\u636e")
            self._draw_time_labels(painter, plot_rect)
            return

        latest_ts = self.samples[-1][0]
        min_ts = latest_ts - self.window_seconds
        visible_samples = [(ts, val) for ts, val in self.samples if ts >= min_ts]
        if not visible_samples:
            visible_samples = list(self.samples)[-2:]

        min_value, max_value = self._compute_value_range([value for _ts, value in visible_samples])

        grid_pen = QPen(QColor("#222933"))
        grid_pen.setStyle(Qt.DashLine)
        painter.setPen(grid_pen)
        for index in range(1, 5):
            y = plot_rect.top() + plot_rect.height() * index / 5.0
            painter.drawLine(plot_rect.left(), int(y), plot_rect.right(), int(y))
        for index in range(1, 4):
            x = plot_rect.left() + plot_rect.width() * index / 4.0
            painter.drawLine(int(x), plot_rect.top(), int(x), plot_rect.bottom())

        def map_point(ts: float, value: float) -> QPointF:
            x_ratio = (ts - min_ts) / max(self.window_seconds, 1e-6)
            y_ratio = (value - min_value) / (max_value - min_value)
            x = plot_rect.left() + x_ratio * plot_rect.width()
            y = plot_rect.bottom() - y_ratio * plot_rect.height()
            return QPointF(x, y)

        if self.baseline_value is not None and min_value <= self.baseline_value <= max_value:
            baseline_y = map_point(latest_ts, self.baseline_value).y()
            painter.setPen(QPen(QColor("#4d607b"), 1.2))
            painter.drawLine(plot_rect.left(), int(baseline_y), plot_rect.right(), int(baseline_y))

        mapped_points = [map_point(ts, value) for ts, value in visible_samples]
        path = self._build_curve_path(mapped_points)

        fill_path = QPainterPath(path)
        fill_path.lineTo(mapped_points[-1].x(), plot_rect.bottom())
        fill_path.lineTo(mapped_points[0].x(), plot_rect.bottom())
        fill_path.closeSubpath()
        fill_gradient = QLinearGradient(0.0, plot_rect.top(), 0.0, plot_rect.bottom())
        fill_color = QColor(self.line_color)
        fill_color.setAlpha(78)
        fill_gradient.setColorAt(0.0, fill_color)
        fill_color = QColor(self.line_color)
        fill_color.setAlpha(10)
        fill_gradient.setColorAt(1.0, fill_color)
        painter.fillPath(fill_path, fill_gradient)

        glow_color = QColor(self.line_color)
        glow_color.setAlpha(70)
        painter.setPen(QPen(glow_color, 5.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)

        painter.setPen(QPen(self.line_color, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)

        latest_point = mapped_points[-1]
        painter.setPen(Qt.NoPen)
        halo = QColor(self.line_color)
        halo.setAlpha(95)
        painter.setBrush(halo)
        painter.drawEllipse(latest_point, 5.0, 5.0)
        painter.setBrush(QColor("#f7fbff"))
        painter.drawEllipse(latest_point, 2.2, 2.2)

        painter.setPen(QColor("#95a1b2"))
        self._draw_value_labels(painter, plot_rect, min_value, max_value)
        self._draw_time_labels(painter, plot_rect)

    def _draw_header(self, painter: QPainter, outer: QRectF) -> None:
        painter.setPen(QColor("#e4ebf4"))
        title_font = QFont(painter.font())
        title_font.setBold(True)
        title_font.setPointSizeF(title_font.pointSizeF() + 0.5)
        painter.setFont(title_font)
        painter.drawText(outer.adjusted(10, 0, -10, 0), Qt.AlignTop | Qt.AlignLeft, self.title)

        current_value = "--"
        if self.samples:
            current_value = self._format_value(self.samples[-1][1])

        badge_text = f"{current_value}{self.y_unit}"
        badge_rect = QRectF(outer.right() - 128.0, outer.top() + 8.0, 116.0, 20.0)
        painter.setPen(QPen(QColor("#435065"), 1.0))
        badge_fill = QColor("#101722")
        badge_fill.setAlpha(220)
        painter.setBrush(badge_fill)
        painter.drawRoundedRect(badge_rect, 10.0, 10.0)

        value_font = QFont(title_font)
        value_font.setBold(False)
        value_font.setPointSizeF(max(8.5, value_font.pointSizeF() - 0.5))
        painter.setFont(value_font)
        painter.setPen(QColor("#b8c6d8"))
        painter.drawText(badge_rect.adjusted(8, 0, -8, 0), Qt.AlignCenter, badge_text)

    def _draw_value_labels(self, painter: QPainter, plot_rect: QRectF, min_value: float, max_value: float) -> None:
        label_rect = plot_rect.adjusted(-40, 0, -4, 0)
        mid_value = (min_value + max_value) / 2.0
        painter.drawText(label_rect.adjusted(0, 0, 0, -4), Qt.AlignTop | Qt.AlignLeft, self._format_value(max_value))
        painter.drawText(label_rect, Qt.AlignVCenter | Qt.AlignLeft, self._format_value(mid_value))
        painter.drawText(label_rect.adjusted(0, 4, 0, 0), Qt.AlignBottom | Qt.AlignLeft, self._format_value(min_value))

    def _draw_time_labels(self, painter: QPainter, plot_rect: QRectF) -> None:
        painter.drawText(plot_rect.adjusted(4, 0, 0, -2), Qt.AlignBottom | Qt.AlignLeft, f"-{int(self.window_seconds)}\u79d2")
        painter.drawText(plot_rect, Qt.AlignBottom | Qt.AlignHCenter, f"-{self._format_seconds(self.window_seconds / 2.0)}")
        painter.drawText(plot_rect.adjusted(0, 0, -4, -2), Qt.AlignBottom | Qt.AlignRight, "\u73b0\u5728")

    def _compute_value_range(self, values: list[float]) -> Tuple[float, float]:
        min_value = min(values)
        max_value = max(values)

        baseline = self.baseline_value
        if baseline is not None:
            min_value = min(min_value, baseline)
            max_value = max(max_value, baseline)
            if self.symmetric_baseline:
                extent = max(abs(max_value - baseline), abs(min_value - baseline), 0.2)
                pad = max(extent * 0.18, 0.05)
                return baseline - extent - pad, baseline + extent + pad

        if abs(max_value - min_value) < 1e-6:
            spread = max(abs(max_value) * 0.1, 1.0 if baseline is None else 0.3)
            max_value += spread
            min_value -= spread

        pad = max((max_value - min_value) * 0.14, 0.04)
        return min_value - pad, max_value + pad

    @staticmethod
    def _build_curve_path(points: list[QPointF]) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(points[0])
        if len(points) == 2:
            path.lineTo(points[1])
            return path

        for index in range(1, len(points)):
            previous = points[index - 1]
            current = points[index]
            control_x = (previous.x() + current.x()) / 2.0
            path.cubicTo(control_x, previous.y(), control_x, current.y(), current.x(), current.y())
        return path

    def _format_value(self, value: float) -> str:
        return f"{value:.{self.decimals}f}"

    @staticmethod
    def _format_seconds(seconds: float) -> str:
        if abs(seconds - round(seconds)) < 1e-6:
            return f"{int(round(seconds))}\u79d2"
        return f"{seconds:.1f}\u79d2"