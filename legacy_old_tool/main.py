import sys
import serial
from serial.tools import list_ports
import cv2
import numpy as np
import pandas as pd
import time
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel, QTextEdit,
                             QGridLayout, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog,
                             QComboBox, QLineEdit, QTabWidget, QGroupBox, QFormLayout,
                             QMessageBox, QStatusBar)
from PyQt5.QtGui import QPixmap, QImage
import pyautogui
from screeninfo import get_monitors
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure


# ------------------ 线程类定义 ------------------

class SerialThread(QThread):
    status_signal = pyqtSignal(str)
    data_received = pyqtSignal(str)

    def __init__(self, port, baudrate, filename):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.filename = filename
        self.running = False
        self.serial_conn = None

    def run(self):
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate)
            with open(self.filename, 'w') as f:
                self.running = True
                while self.running:
                    if self.serial_conn.in_waiting:
                        data = self.serial_conn.readline().decode('utf-8', errors='ignore')
                        f.write(data)
                        f.flush()
                        self.data_received.emit(data.strip())
        except Exception as e:
            self.status_signal.emit(f"串口错误: {str(e)}")
        finally:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()

    def stop(self):
        self.running = False


class CameraThread(QThread):
    frame_ready = pyqtSignal(np.ndarray, int)
    status_signal = pyqtSignal(str)

    def __init__(self, camera_index, filename):
        super().__init__()
        self.camera_index = camera_index
        self.filename = filename
        self.running = False
        self.writer = None

    def run(self):
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            self.status_signal.emit(f"摄像头{self.camera_index}无法打开")
            return

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.writer = cv2.VideoWriter(
            self.filename,
            cv2.VideoWriter_fourcc(*'XVID'),
            20.0,
            (width, height)
        )

        self.running = True
        while self.running:
            ret, frame = cap.read()
            if ret:
                self.writer.write(frame)
                self.frame_ready.emit(frame, self.camera_index)
            else:
                self.status_signal.emit(f"摄像头{self.camera_index}读取失败")
                break

        cap.release()
        self.writer.release()

    def stop(self):
        self.running = False


class ScreenRecordThread(QThread):
    status_signal = pyqtSignal(str)

    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        self.running = False
        self.writer = None

    def run(self):
        try:
            monitors = get_monitors()
            if not monitors:
                self.status_signal.emit("无法获取屏幕信息")
                return

            monitor = monitors[0]
            screen_size = (monitor.width, monitor.height)

            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            self.writer = cv2.VideoWriter(
                self.filename,
                fourcc,
                10.0,
                screen_size
            )

            self.running = True
            while self.running:
                img = pyautogui.screenshot()
                frame = np.array(img)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.writer.write(frame)
                time.sleep(0.1)  # 控制帧率 10fps

        except Exception as e:
            self.status_signal.emit(f"录屏错误: {str(e)}")
        finally:
            if self.writer:
                self.writer.release()

    def stop(self):
        self.running = False


# ------------------ 离线回放图表类 ------------------

class MplCanvas(FigureCanvas):
    """Matplotlib图表画布"""
    def __init__(self, parent=None, width=8, height=5, dpi=100):
        self.fig, self.axes = plt.subplots(figsize=(width, height), dpi=dpi)
        super(MplCanvas, self).__init__(self.fig)

    def plot_data(self, df, y_column):
        self.axes.clear()
        x_data = df["时间"]
        y_data = df[y_column]

        # 自动处理时间列
        try:
            x_data = pd.to_datetime(x_data)
            x_label = "时间"
        except Exception:
            try:
                x_data = pd.to_numeric(x_data)
                x_label = "数值"
            except:
                x_data = np.arange(len(df))
                x_label = "帧索引"

        self.axes.plot(x_data, y_data)
        self.axes.set_xlabel(x_label)
        self.axes.set_ylabel(y_column)
        self.axes.set_title(f"{y_column} 随时间变化")
        self.axes.grid(True)
        self.fig.autofmt_xdate()
        self.draw()


# ------------------ 主窗口类 ------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("数据录制与回放上位机")
        self.setGeometry(100, 100, 1200, 800)

        # 状态变量
        self.threads = []
        self.is_recording = False
        self.data_df = None
        self.recording_start_time = None
        self.timer = None

        # 主控件
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        # 在线录制选项卡
        self.online_widget = QWidget()
        self.tab_widget.addTab(self.online_widget, "在线录制")
        self.init_online_ui()

        # 离线回放选项卡
        self.offline_widget = QWidget()
        self.tab_widget.addTab(self.offline_widget, "离线回放")
        self.init_offline_ui()

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def init_online_ui(self):
        layout = QVBoxLayout()

        # 串口配置区域
        serial_group = QGroupBox("串口配置")
        serial_layout = QHBoxLayout()
        self.port_combo = QComboBox()
        self.baudrate_input = QLineEdit("115200")
        refresh_btn = QPushButton("刷新端口")
        refresh_btn.clicked.connect(self.update_serial_ports)
        serial_layout.addWidget(QLabel("串口端口:"))
        serial_layout.addWidget(self.port_combo)
        serial_layout.addWidget(QLabel("波特率:"))
        serial_layout.addWidget(self.baudrate_input)
        serial_layout.addWidget(refresh_btn)
        serial_group.setLayout(serial_layout)
        layout.addWidget(serial_group)

        # 摄像头预览区域
        self.camera_group = QGroupBox("摄像头预览")
        self.camera_layout = QGridLayout()
        self.camera_labels = []
        for i in range(4):
            label = QLabel(f"摄像头{i + 1}未连接")
            label.setAlignment(Qt.AlignCenter)
            label.setFixedSize(300, 200)
            label.setStyleSheet("border: 1px solid #ccc; padding: 5px;")
            self.camera_labels.append(label)
            self.camera_layout.addWidget(label, i // 2, i % 2)
        self.camera_group.setLayout(self.camera_layout)
        layout.addWidget(self.camera_group)

        # 串口数据实时显示区域
        self.serial_data_display = QTextEdit()
        self.serial_data_display.setReadOnly(True)
        self.serial_data_display.setMaximumHeight(150)
        layout.addWidget(QLabel("串口数据实时显示:"))
        layout.addWidget(self.serial_data_display)

        # 控制按钮
        control_panel = QWidget()
        control_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始测试")
        self.stop_btn = QPushButton("结束测试")
        self.stop_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_test)
        self.stop_btn.clicked.connect(self.stop_test)
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_panel.setLayout(control_layout)
        layout.addWidget(control_panel)

        self.online_widget.setLayout(layout)
        self.update_serial_ports()

    def init_offline_ui(self):
        layout = QVBoxLayout()

        # 文件选择区域
        file_group = QGroupBox("CSV文件选择")
        file_layout = QFormLayout()
        self.file_path_input = QLineEdit()
        self.file_path_input.setReadOnly(True)
        self.select_file_btn = QPushButton("选择文件")
        file_layout.addRow("文件路径:", self.file_path_input)
        file_layout.addRow(self.select_file_btn)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # 纵轴选择区域
        plot_group = QGroupBox("图表设置")
        plot_layout = QFormLayout()
        self.y_combo = QComboBox()
        self.plot_btn = QPushButton("绘制图表")
        plot_layout.addRow("纵轴数据列:", self.y_combo)
        plot_layout.addRow(self.plot_btn)
        plot_group.setLayout(plot_layout)
        layout.addWidget(plot_group)

        # 图表区域
        self.canvas = MplCanvas(self, width=8, height=5, dpi=100)
        self.toolbar = NavigationToolbar(self.canvas, self.offline_widget)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        # 信号连接
        self.select_file_btn.clicked.connect(self.select_csv_file)
        self.plot_btn.clicked.connect(self.plot_selected_data)

        self.offline_widget.setLayout(layout)

    def update_serial_ports(self):
        """更新可用串口列表"""
        self.port_combo.clear()
        ports = list_ports.comports()
        for port in ports:
            self.port_combo.addItem(port.device)

    def start_test(self):
        """开始录制按钮点击事件"""
        if self.is_recording:
            return

        save_dir = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if not save_dir:
            self.statusBar().showMessage("未选择保存目录，录制取消")
            return

        port = self.port_combo.currentText()
        try:
            baudrate = int(self.baudrate_input.text())
        except ValueError:
            self.statusBar().showMessage("波特率必须为整数")
            return

        # 创建线程
        serial_thread = SerialThread(port, baudrate, f"{save_dir}/serial_data.txt")
        serial_thread.status_signal.connect(self.show_status)
        serial_thread.data_received.connect(self.handle_serial_data)
        self.threads.append(serial_thread)

        for i in range(4):
            camera_thread = CameraThread(i, f"{save_dir}/camera_{i + 1}.avi")
            camera_thread.frame_ready.connect(self.update_camera_view)
            camera_thread.status_signal.connect(lambda msg, idx=i: self.handle_camera_error(msg, idx))
            self.threads.append(camera_thread)

        screen_thread = ScreenRecordThread(f"{save_dir}/screen_record.avi")
        screen_thread.status_signal.connect(self.show_status)
        self.threads.append(screen_thread)

        # 启动线程
        for thread in self.threads:
            thread.start()

        self.is_recording = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.statusBar().showMessage(f"录制开始，保存路径: {save_dir}")

        # 启动录制时间计时器
        self.recording_start_time = time.time()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_recording_time)
        self.timer.start(1000)

    def stop_test(self):
        """结束录制按钮点击事件"""
        if not self.is_recording:
            return

        for thread in self.threads:
            thread.stop()

        for thread in self.threads:
            thread.wait()

        self.threads.clear()
        self.is_recording = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.statusBar().showMessage("录制已停止")

        # 停止时间计时器
        if self.timer:
            self.timer.stop()
            self.timer.deleteLater()
            self.timer = None

        # 清空摄像头预览
        for label in self.camera_labels:
            label.setPixmap(QPixmap())
            label.setText("未连接")
            label.setStyleSheet("border: 1px solid #ccc; padding: 5px;")

    def update_recording_time(self):
        """更新录制时间"""
        if self.is_recording and self.recording_start_time:
            elapsed = time.time() - self.recording_start_time
            mins, secs = divmod(int(elapsed), 60)
            self.statusBar().showMessage(f"录制时间: {mins}分{secs}秒")

    def update_camera_view(self, frame, camera_index):
        """更新摄像头画面"""
        if camera_index < len(self.camera_labels):
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
            scaled_pixmap = QPixmap.fromImage(qt_image).scaled(
                self.camera_labels[camera_index].size(), Qt.KeepAspectRatioByExpanding
            )
            self.camera_labels[camera_index].setPixmap(scaled_pixmap)
            self.camera_labels[camera_index].setText("")
            self.camera_labels[camera_index].setStyleSheet("border: 1px solid #00c000; padding: 5px;")

    def handle_camera_error(self, msg, camera_index):
        """处理摄像头错误"""
        if camera_index < len(self.camera_labels):
            self.camera_labels[camera_index].setText(f"摄像头{camera_index + 1}错误:\n{msg}")
            self.camera_labels[camera_index].setStyleSheet("border: 1px solid red; background-color: #ffe0e0;")

    def handle_serial_data(self, data):
        """处理串口接收到的数据"""
        self.serial_data_display.append(data)

    def show_status(self, message):
        """显示状态信息"""
        self.statusBar().showMessage(message)

    def select_csv_file(self):
        """选择CSV文件"""
        file_path, _ = QFileDialog.getOpenFileName(self, "选择CSV文件", "", "CSV文件 (*.csv)")
        if file_path:
            try:
                self.data_df = pd.read_csv(file_path)
                if "时间" not in self.data_df.columns:
                    raise ValueError("CSV文件中没有'时间'列")

                self.file_path_input.setText(file_path)
                self.y_combo.clear()
                self.y_combo.addItems([col for col in self.data_df.columns if col != "时间"])
                self.show_status("CSV文件加载成功")
            except Exception as e:
                self.show_status(f"加载CSV失败: {str(e)}")
                QMessageBox.critical(self, "错误", f"加载CSV失败: {str(e)}")

    def plot_selected_data(self):
        """绘制选择的数据列"""
        if self.data_df is None:
            self.show_status("请先选择CSV文件")
            return

        y_col = self.y_combo.currentText()
        if not y_col:
            self.show_status("请选择一个数据列")
            return

        self.canvas.plot_data(self.data_df, y_col)
        self.show_status(f"图表已绘制: {y_col} 随时间变化")


# ------------------ 主程序入口 ------------------

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
