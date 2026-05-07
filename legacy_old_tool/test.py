import asyncio
import json
import os
import re
import signal

import copy

import bleak
import asyncqt
import qasync
import traceback
from matplotlib.figure import Figure

import device_model
import uuid
from datetime import datetime

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
                             QMessageBox, QStatusBar, QTextBrowser, QCheckBox)
from PyQt5.QtGui import QPixmap, QImage
import pyautogui
from screeninfo import get_monitors
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

import os
import time
import subprocess
import platform

import cv2
import os
import pandas as pd
from PyQt5.QtCore import pyqtSignal, QObject, QThread
from PyQt5.QtWidgets import QProgressDialog, QMessageBox
from PIL import ImageGrab


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

        width = 640
        height = 480
        self.writer = cv2.VideoWriter(
            self.filename,
            cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'),
            25.0,
            (width, height)
        )

        self.running = True
        while self.running:
            ret, frame = cap.read()
            if ret:
                if frame.ndim == 3:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                elif frame.ndim == 2:
                    frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

                self.writer.write(frame)
                self.frame_ready.emit(frame, self.camera_index)
                del frame
            else:
                self.status_signal.emit(f"摄像头{self.camera_index}读取失败")
                break

        cap.release()
        self.writer.release()

    def stop(self):
        self.running = False


class ScreenRecordThread(QThread):
    progress_signal = pyqtSignal(str, int, int)  # message, current, total
    finished_signal = pyqtSignal()
    status_signal = pyqtSignal(str)

    def __init__(self, save_dir, screen_size):
        super().__init__()
        self.save_dir = save_dir
        self.screen_size = screen_size
        self.is_recording = False
        self.screen_filename = os.path.join(save_dir, "screen_record.mp4")

    def run(self):

        try:
            monitors = get_monitors()
            if not monitors:
                self.status_signal.emit("无法获取屏幕信息")
                return

            monitor = monitors[0]
            screen_size = (monitor.width, monitor.height)

            cmd = "ffmpeg -f gdigrab -framerate 30 -offset_x 0 -offset_y 0 -video_size {}x{} -i desktop " \
                  "-c:v libx264 -preset ultrafast {}".format(monitor.width, monitor.height, self.save_dir)

            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # fourcc = cv2.VideoWriter_fourcc(*'XVID')
            # self.writer = cv2.VideoWriter(
            #     self.save_dir,
            #     fourcc,
            #     20.0,
            #     screen_size
            # )
            #
            # self.running = True
            # while self.running:
            #     img = ImageGrab.grab()
            #     frame = np.array(img)
            #     self.writer.write(frame)
            #     del frame
            #     del img
            #     time.sleep(0.01)

        except Exception as e:
            self.status_signal.emit(f"录屏错误: {str(e)}")
        finally:
            pass
            # if self.writer:
            #     self.writer.release()

    def stop(self):
        self.running = False
        try:
            self.process.send_signal(signal.SIGINT)
        except:
            pass

        try:
            self.process.terminate()
            self.process.wait()
        except:
            pass
        try:
            self.process.kill()
        except:
            pass
        print(self.process)


def modify_data(data_info):
    mapping = {
        "AccX": "加速度X(g)",
        "AccY": "加速度Y(g)",
        "AccZ": "加速度Z(g)",
        "AsX": "角速度X(°/s)",
        "AsY": "角速度Y(°/s)",
        "AsZ": "角速度Z(°/s)",
        "AngX": "角速度X(°/s)",
        "AngY": "角速度Y(°/s)",
        "AngZ": "角速度Z(°/s)",
        "HX": "角度X(°)",
        "HY": "角度Y(°)",
        "HZ": "角度Z(°)",
    }

    modified_data = {
        "时间": time.time()
    }

    for key in data_info.keys():
        if key in mapping.keys():
            modified_data[mapping[key]] = data_info[key]

    for key in mapping.keys():
        if key not in data_info.keys():
            modified_data[mapping[key]] = 0

    return modified_data


class IMURecordThread(QThread):
    start_matching = pyqtSignal(object)
    start_recording = pyqtSignal(object)

    def __init__(self, save_dir):
        super().__init__()
        self.save_dir = save_dir
        self.is_recording = False
        self.BLE_device = None
        self.data = dict()

    # 数据更新时会调用此方法 This method will be called when data is updated
    def update_data(self, device_model):
        try:
            data_info = device_model.deviceData
            modified_data = modify_data(data_info)
            for key in modified_data:
                if key in self.data:
                    self.data[key].append(modified_data[key])
                else:
                    self.data[key] = [modified_data[key]]
            self.start_matching.emit("IMU Data on Received...")
        except:
            print(traceback.format_exc())

    @property
    def address(self):
        return "CF:17:7C:C4:87:E7"

    async def scan(self):
        print("Searching for Bluetooth devices......")
        try:
            devices = await bleak.BleakScanner.discover(timeout=20.0)
            print("Search ended")
            for d in devices:
                if d.name is not None and d.address == self.address:
                    print(d)
                    self.BLE_device = d
                    self.device = device_model.DeviceModel("MyBle5.0", self.BLE_device, self.update_data)
                    self.start_matching.emit("{}".format(d.name))
        except Exception as ex:
            print("Bluetooth search failed to start")
            print(traceback.format_exc())

    def store_data(self, run_start_time, run_end_time):
        json_file = os.path.join(self.save_dir, "imu_data.json")
        csv_file = os.path.join(self.save_dir, "imu_data.csv")

        data_rn = copy.deepcopy(self.data)
        start_idx = 0
        end_idx = -1

        for i in range(len(data_rn["时间"]) - 1):
            if data_rn["时间"][i] <= run_start_time <= data_rn["时间"][i + 1]:
                start_idx = i

            if data_rn["时间"][i] <= run_end_time <= data_rn["时间"][i + 1]:
                end_idx = i

        final_data = dict()

        for key in data_rn:
            final_data[key] = data_rn[key][start_idx:end_idx]

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)

        df = pd.DataFrame(final_data)
        df.to_csv(csv_file, encoding="utf-8")
        self.data = dict()

    async def run(self):
        await self.device.openDevice()

    def stop(self):
        self.device.closeDevice()



# ------------------ 离线回放图表类 ------------------

class MplCanvas(FigureCanvas):
    """Matplotlib图表画布，支持高亮时间段"""
    def __init__(self, parent=None, width=8, height=5, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        print("aaaaaaaaaaa")
        super(MplCanvas, self).__init__(self.fig)

    def plot_data(self, df, y_column, time_ranges=None):
        if time_ranges is None:
            time_ranges = []  # 支持多对时间段，每个为 (start_time, end_time)
        self.axes.clear()
        x_data = df["时间"]
        x_data = [float(el) for el in x_data]
        y_data = df[y_column]
        print(x_data)
        print(type(x_data[0]))
        # 自动处理时间列
        try:
            x_data = pd.to_datetime(x_data, unit="s", utc=True)
            x_label = "时间"
            x_data = x_data.tz_convert("Asia/Shanghai")
        except Exception:
            try:
                x_data = pd.to_numeric(x_data)
                x_label = "数值"
            except:
                x_data = np.arange(len(df))
                x_label = "帧索引"

        # 绘制主曲线
        self.axes.plot(x_data, y_data, label=y_column)
        # 如果有时间范围，高亮它们
        for start_time, end_time in time_ranges:
            # 如果 start/end 是 float，也转为 pd.Timestamp
            try:
                start_dt = pd.to_datetime(start_time, unit='s')
                end_dt = pd.to_datetime(end_time, unit='s')
                self.axes.axvspan(start_dt, end_dt, color='yellow', alpha=0.3, label='高亮区域')
                print(type(start_time), end_time)
                print(start_dt, end_dt)
            except Exception as e:
                print(f"无法高亮区间 {start_time} - {end_time}: {e}")
        # 设置标签
        print(x_label)
        print(x_data)
        self.axes.set_xlabel(x_label)
        self.axes.set_ylabel(y_column)
        self.axes.set_title(f"{y_column} 随时间变化")
        self.axes.grid(True)
        self.fig.autofmt_xdate()
        # 只显示一次 '高亮区域' 的图例
        handles, labels = self.axes.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        self.axes.legend(by_label.values(), by_label.keys())
        self.draw()


# ------------------ 主窗口类 ------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("数据录制与回放上位机")
        self.setGeometry(100, 100, 1200, 800)
        self.screen_record_thread = None
        self.imu_thread = None
        self.data_clipper_thread = None
        self.progress_dialog = None
        self.run_start_time = None

        # 状态变量
        self.screen_recording_files = list()
        self.file_name_list = list()
        self.threads = []
        self.is_recording = False
        self.data_df = None
        self.issue_json = None
        self.recording_start_time = None
        self.timer = None
        self.available_cameras = []
        self.save_dir = None
        self.issue_manager = None
        self.time_ranges = []
        self.device = IMURecordThread(self.save_dir)

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



    def detect_available_cameras(self):
        available_cameras = []
        for i in range(10):  # 假设最大摄像头数量为10，可以根据需要调整
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                cap.release()
                available_cameras.append(i)
        return available_cameras

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

        ble_group = QGroupBox("蓝牙连接")
        ble_layout = QHBoxLayout()
        connect_imu = QPushButton("链接蓝牙设备")
        connect_imu.clicked.connect(self.connect_imu)
        start_imu_btn = QPushButton("开启蓝牙录制")
        start_imu_btn.clicked.connect(self.start_imu_recording)
        ble_layout.addWidget(start_imu_btn)
        ble_layout.addWidget(connect_imu)

        self.imu_display = QLineEdit()
        self.imu_display.setReadOnly(True)
        self.device.start_matching.connect(self.imu_display.setText)

        ble_group.setLayout(ble_layout)
        layout.addWidget(ble_group)
        layout.addWidget(self.imu_display)

        # 检测可用摄像头
        self.available_cameras = self.detect_available_cameras()

        # 摄像头选择与预览区域
        camera_group = QGroupBox("摄像头选择与预览")
        camera_layout = QHBoxLayout()

        self.camera_checkboxes = []
        self.camera_labels = []

        for i in self.available_cameras:
            sub_cam_group = QGroupBox(f"摄像头{i + 1}")
            sub_cam_layout = QVBoxLayout()
            checkbox = QCheckBox(f"摄像头{i + 1}")
            sub_cam_layout.addWidget(checkbox)
            self.camera_checkboxes.append(checkbox)
            label = QLabel(f"摄像头{i + 1}未连接")
            label.setAlignment(Qt.AlignCenter)
            label.setFixedSize(600, 400)
            label.setStyleSheet("border: 1px solid #ccc; padding: 5px;")
            self.camera_labels.append(label)
            sub_cam_layout.addWidget(label)
            sub_cam_group.setLayout(sub_cam_layout)
            camera_layout.addWidget(sub_cam_group)

        camera_group.setLayout(camera_layout)
        layout.addWidget(camera_group)

        # # 串口数据实时显示区域
        # self.serial_data_display = QTextEdit()
        # self.serial_data_display.setReadOnly(True)
        # self.serial_data_display.setMaximumHeight(150)
        # layout.addWidget(QLabel("串口数据实时显示:"))
        # layout.addWidget(self.serial_data_display)

        # 打点区域
        issue_group = QGroupBox("打点功能")
        issue_layout = QVBoxLayout()

        # 简易打点
        self.simple_issue_name_input = QLineEdit("简易点位")
        simple_issue_btn = QPushButton("简易打点")
        simple_issue_btn.clicked.connect(self.add_simple_issue)

        simple_issue_layout = QHBoxLayout()
        simple_issue_layout.addWidget(QLabel("点位名称:"))
        simple_issue_layout.addWidget(self.simple_issue_name_input)
        simple_issue_layout.addWidget(simple_issue_btn)

        issue_layout.addLayout(simple_issue_layout)


        # 显示最近打点信息
        self.last_issues_label = QLabel("最近的打点信息:")
        self.issues_label = QTextBrowser()
        issue_layout.addWidget(self.last_issues_label)
        issue_layout.addWidget(self.issues_label)
        issue_group.setLayout(issue_layout)
        layout.addWidget(issue_group)

        # 控制按钮
        control_panel = QWidget()
        control_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始测试")
        self.stop_btn = QPushButton("结束测试")
        self.stop_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_recording)
        self.stop_btn.clicked.connect(self.stop_recording)
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_panel.setLayout(control_layout)
        layout.addWidget(control_panel)

        self.online_widget.setLayout(layout)
        self.update_serial_ports()

    def connect_imu(self):
        asyncio.ensure_future(self.device.scan())

    def start_imu_recording(self):
        asyncio.ensure_future(self.device.device.openDevice())

    def update_serial_ports(self):
        """更新可用串口列表"""
        self.port_combo.clear()
        ports = list_ports.comports()
        for port in ports:
            self.port_combo.addItem(port.device)

    def start_recording(self):
        if self.is_recording:
            return

        self.save_dir = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if not self.save_dir:
            self.statusBar().showMessage("未选择保存目录，录制取消")
            return
        self.device.save_dir = self.save_dir

        port = self.port_combo.currentText()
        try:
            baudrate = int(self.baudrate_input.text())
        except ValueError:
            self.statusBar().showMessage("波特率必须为整数")
            return

        # 创建打点记录文件夹和记录文件
        issue_records_folder = os.path.join(self.save_dir, "issue_records")
        if not os.path.exists(issue_records_folder):
            os.makedirs(issue_records_folder)

        # 创建打点管理器
        self.issue_manager = IssueManager(self.save_dir)

        # 创建串口线程
        serial_thread = SerialThread(port, baudrate, f"{self.save_dir}/serial_data.txt")
        serial_thread.status_signal.connect(self.show_status)
        serial_thread.data_received.connect(self.handle_serial_data)
        self.threads.append(serial_thread)

        # 获取用户选择的摄像头
        selected_cameras = [i for i, checkbox in enumerate(self.camera_checkboxes) if
                            checkbox.isChecked() and i in self.available_cameras]

        for camera_index in selected_cameras:

            camera_recording_file = f"{self.save_dir}/camera_{camera_index + 1}.avi"
            camera_thread = CameraThread(camera_index, camera_recording_file)
            camera_thread.frame_ready.connect(self.update_camera_view)
            camera_thread.status_signal.connect(lambda msg, idx=camera_index: self.handle_camera_error(msg, idx))
            self.threads.append(camera_thread)
            self.screen_recording_files.append(camera_recording_file)

        # 创建屏幕录制线程
        screen_size = (1920, 1080)
        screen_recording_file = f"{self.save_dir}/screen_record.avi"
        self.screen_recording_files.append(screen_recording_file)
        self.screen_record_thread = ScreenRecordThread(screen_recording_file, screen_size)
        self.screen_record_thread.progress_signal.connect(self.update_progress)
        self.screen_record_thread.finished_signal.connect(self.recording_completed)
        self.screen_record_thread.status_signal.connect(self.show_status)
        self.threads.append(self.screen_record_thread)

        # 启动所有线程
        for thread in self.threads:
            thread.start()

        self.is_recording = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.statusBar().showMessage(f"录制开始，保存路径: {self.save_dir}")

        # 启动录制时间计时器
        self.recording_start_time = time.time()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_recording_time)
        self.timer.start(1000)

    def stop_recording(self):
        try:
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
            try:
                self.device.store_data(run_start_time=self.recording_start_time, run_end_time=time.time())
            except:
                pass
            # 显示进度对话框
            self.show_progress_dialog()
        except:
            print(traceback.format_exc())

    def show_progress_dialog(self):
        self.progress_dialog = QProgressDialog("数据剪切正在进行中...", "取消", 0, 100, self)
        self.progress_dialog.setWindowTitle("剪切进度")
        self.progress_dialog.setWindowModality(Qt.WindowModal)  # 保持对话框 modal
        self.progress_dialog.canceled.connect(self.cancel_clip_data)

        self.data_clipper_thread = DataClipperThread(self.save_dir, self.screen_recording_files)
        self.data_clipper_thread.progress_signal.connect(self.update_progress)
        self.data_clipper_thread.finished_signal.connect(self.clip_completed)
        self.data_clipper_thread.start()

    def update_progress(self, message, current, total):
        if total > 0:
            percentage = (current + 1) / total * 100
            self.progress_dialog.setValue(int(percentage))
            self.statusBar().showMessage(message)
        else:
            self.statusBar().showMessage(message)

    def clip_completed(self):
        self.progress_dialog.setValue(100)
        self.progress_dialog.close()
        QMessageBox.information(self, "完成", "数据剪切完成！")

    def cancel_clip_data(self):
        if self.data_clipper_thread:
            self.data_clipper_thread.terminate()
            self.progress_dialog.close()
            QMessageBox.warning(self, "取消", "数据剪切已取消")
            self.data_clipper_thread = None

    def update_timer_display(self):
        elapsed_time = self.timer.interval() * self.timer.remainingTime() // 1000
        h, r = divmod(elapsed_time, 3600)
        m, s = divmod(r, 60)
        time_str = f"{h:02}:{m:02}:{s:02}"
        self.statusBar().showMessage(f"录制进行中... 已录制 {time_str}")

    def show_clip_progress(self, message):
        self.statusBar().showMessage(message)
        QMessageBox.information(self, "进度", message)

    def update_recording_time(self):
        if self.is_recording and self.recording_start_time:
            elapsed = time.time() - self.recording_start_time
            mins, secs = divmod(int(elapsed), 60)
            self.statusBar().showMessage(f"录制时间: {mins}分{secs}秒")

    def update_camera_view(self, frame, camera_index):
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
        if camera_index < len(self.camera_labels):
            self.camera_labels[camera_index].setText(f"摄像头{camera_index + 1}错误:\n{msg}")
            self.camera_labels[camera_index].setStyleSheet("border: 1px solid red; background-color: #ffe0e0;")

    def handle_serial_data(self, data):
        self.serial_data_display.append(data)

    def show_status(self, message):
        """显示状态信息"""
        self.statusBar().showMessage(message)

    def add_simple_issue(self):
        if not self.is_recording:
            self.statusBar().showMessage("请先开始测试")
            return

        issue_name = self.simple_issue_name_input.text()
        if not issue_name.strip():
            self.statusBar().showMessage("点位名称不能为空")
            return

        current_time = time.time()
        start_time = current_time - 30
        end_time = current_time + 10

        start_time_str = datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S.%f')
        end_time_str = datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S.%f')

        issue_id = issue_name + "_" + str(uuid.uuid4())
        issue_folder_path = os.path.join(self.save_dir, "issue_records", issue_id)
        os.makedirs(issue_folder_path)

        issue = Issue(
            name=issue_name,
            start_time=start_time,
            end_time=end_time,
            mode="简易点位",
            folder_path=issue_folder_path,
            start_time_str=start_time_str,
            end_time_str=end_time_str,
            run_start_time=self.recording_start_time
        )

        self.save_issue(issue)

    def save_issue(self, issue):
        if self.issue_manager is None:
            self.statusBar().showMessage("请先开始测试")
            return

        issue_info_file = os.path.join(issue.folder_path, "issue_info.json")
        with open(issue_info_file, 'w', encoding='utf-8') as f:
            json.dump(issue.to_dict(), f, ensure_ascii=False, indent=4)

        self.issue_manager.add_issue(issue)

        # 更新UI显示
        self.update_issues_display(issue)

    def update_issues_display(self, issue):
        self.issues_label.append(json.dumps(issue.to_dict(), ensure_ascii=False, indent=4))

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

        # 文件选择区域
        file_group = QGroupBox("打点JSON文件选择")
        file_layout = QFormLayout()
        self.json_path_input = QLineEdit()
        self.json_path_input.setReadOnly(True)
        self.select_json_btn = QPushButton("选择文件")
        file_layout.addRow("文件路径:", self.json_path_input)
        file_layout.addRow(self.select_json_btn)
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
        self.select_json_btn.clicked.connect(self.select_json_file)
        self.plot_btn.clicked.connect(self.plot_selected_data)

        self.offline_widget.setLayout(layout)

    def select_json_file(self):
        """选择json文件"""
        file_path, _ = QFileDialog.getOpenFileName(self, "选择json文件", "", "JSON文件 (*.json)")
        if file_path:
            try:
                print(file_path)
                with open(file_path, "r", encoding="utf-8") as f:
                    self.issue_json = json.loads(f.read())
                    print(self.issue_json)
                for entry in self.issue_json:
                    print(entry)
                    start = entry.get("start_time")
                    end = entry.get("end_time")
                    if start is not None and end is not None:
                        self.time_ranges.append((start, end))

                self.json_path_input.setText(file_path)
                self.show_status("JSON文件加载成功")
            except Exception as e:
                self.show_status(f"加载JSON失败: {str(e)}")
                QMessageBox.critical(self, "错误", f"加载JSON失败: {str(e)}")

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

    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if not folder_path:
            self.statusBar().showMessage("未选择文件夹")
            return

        self.file_path_input.setText(folder_path)

        issue_records_folder = os.path.join(folder_path, "issue_records")
        if not os.path.exists(issue_records_folder):
            self.statusBar().showMessage("文件夹不包含点位记录")
            return

        issues_file = os.path.join(issue_records_folder, "issues.json")
        if not os.path.exists(issues_file):
            self.statusBar().showMessage("文件夹不包含点位记录")
            return

        with open(issues_file, 'r', encoding='utf-8') as f:
            self.issues = json.load(f)

        self.show_status("文件夹加载成功")

    def plot_selected_data(self):
        """绘制选择的数据列"""
        if self.data_df is None:
            self.show_status("请先选择CSV文件")
            return

        y_col = self.y_combo.currentText()
        if not y_col:
            self.show_status("请选择一个数据列")
            return
        try:
            self.canvas.plot_data(self.data_df, y_col, self.time_ranges)
        except:
            print(traceback.format_exc())
        self.show_status(f"图表已绘制: {y_col} 随时间变化")

    def recording_completed(self):
        self.statusBar().showMessage("录制已完成")


class Issue:
    def __init__(self, name, start_time, end_time, mode, folder_path, start_time_str, end_time_str, run_start_time, score,
                 info=""):
        self.name = name
        self.start_time = start_time
        self.end_time = end_time
        self.mode = mode
        self.folder_path = folder_path
        self.info = info
        self.start_time_str = start_time_str
        self.end_time_str = end_time_str
        self.run_start_time = run_start_time
        self.score = score

    def to_dict(self):
        return {
            "name": self.name,
            "start_time_str": self.start_time,
            "end_time_str": self.end_time,
            "mode": self.mode,
            "info": self.info,
            "folder_path": self.folder_path,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "run_start_time": self.run_start_time,
            "score": self.score,
        }


class IssueManager:
    def __init__(self, save_dir):
        self.save_dir = save_dir
        self.issues_file = os.path.join(save_dir, "issue_records", "issues.json")
        self.issues = []
        self.load_issues()

    def load_issues(self):
        issue_records_folder = os.path.join(self.save_dir, "issue_records")
        if not os.path.exists(issue_records_folder):
            os.makedirs(issue_records_folder)
            return

        if os.path.exists(self.issues_file):
            with open(self.issues_file, 'r', encoding='utf-8') as f:
                self.issues = [Issue(**issue) for issue in json.load(f)]

    def save_issues(self):
        with open(self.issues_file, 'w', encoding='utf-8') as f:
            json.dump([issue.to_dict() for issue in self.issues], f, ensure_ascii=False, indent=4)

    def add_issue(self, issue):
        self.issues.append(issue)
        self.save_issues()

    def get_issues(self):
        return self.issues


class DataClipperThread(QThread):
    progress_signal = pyqtSignal(str, int, int)  # message, current, total
    finished_signal = pyqtSignal()

    def __init__(self, save_dir, recording_files):
        super().__init__()
        self.save_dir = save_dir
        self.recording_files = recording_files
        self.screen_filename = os.path.join(save_dir, "screen_record.avi")
        self.serial_filename = os.path.join(save_dir, "serial_data.txt")
        with open(os.path.join(self.save_dir, "imu_data.json"), "r", encoding="utf-8") as f:
            self.imu_data = json.loads(f.read())
        self.issue_manager = IssueManager(save_dir)
        self.issues = self.issue_manager.get_issues()

    def run(self):
        try:
            total_issues = len(self.issues)
            for index, issue in enumerate(self.issues):
                issue_folder_path = issue.folder_path
                for vedio in self.recording_files:
                    # 剪切录屏视频
                    target_recording = os.path.join(self.save_dir, vedio.split('/')[-1])
                    des_recording = os.path.join(issue_folder_path, vedio.split('/')[-1])
                    print(des_recording)
                    self.clip_video(target_recording, des_recording,
                                    issue.start_time - issue.run_start_time, issue.end_time - issue.run_start_time, index,
                                    total_issues)

                self.clip_imu_data(self.imu_data, issue.start_time, issue.end_time, issue_folder_path)
                # # 剪切串口数据
                # serial_clip_path = os.path.join(issue_folder_path, "serial_clip.txt")
                # print(serial_clip_path)
                # self.clip_serial_data(self.serial_filename, serial_clip_path, issue.start_time, issue.end_time, index,
                #                       total_issues)

            self.finished_signal.emit()
        except Exception as e:
            print(e, traceback.format_exc())
            self.progress_signal.emit(f"剪切过程出错: {str(e)}", len(self.issues), len(self.issues))
            self.finished_signal.emit()

    def clip_video(self, input_path, output_path, start_time, end_time, current, total):
        try:
            self.progress_signal.emit(f"开始剪切录屏 {current + 1}/{total}", current, total)

            if not os.path.exists(input_path):
                raise FileNotFoundError(f"视频文件不存在: {input_path}")

            if start_time < 0:
                start_time = 0

            # 使用 ffmpeg 命令剪切视频
            command = [
                'ffmpeg',
                '-i', input_path,
                '-ss', str(start_time),
                '-to', str(end_time),
                '-c:v', 'libx264',
                '-c:a', 'aac',
                output_path
            ]

            self.progress_signal.emit(rf"FFmpeg Command: {' '.join(command)}", current, total)
            print(f"FFmpeg Command: {' '.join(command)}")  # 输出 FFmpeg 命令

            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate()

            # 解析 FFmpeg 输出以获取进度信息
            progress_pattern = re.compile(r'time=(\d+:\d+:\d+\.\d+)')
            for line in stderr.split('\n'):
                match = progress_pattern.search(line)
                if match:
                    progress_time = match.group(1)
                    # 假设总时长已知，计算进度百分比
                    # 这里需要根据实际总时长进行计算
                    self.progress_signal.emit(f"剪切录屏进度 {current + 1}/{total}: {progress_time}", current, total)

            if stderr:
                self.progress_signal.emit(f"FFmpeg 错误: {stderr}", current, total)
                print(f"FFmpeg 错误: {stderr}")  # 输出 FFmpeg 错误信息

            if stdout:
                self.progress_signal.emit(f"FFmpeg 输出: {stdout}", current, total)
                print(f"FFmpeg 输出: {stdout}")  # 输出 FFmpeg 输出信息

            if process.returncode != 0:
                raise Exception(f"FFmpeg 剪切视频失败: {stderr}")

            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                raise Exception(f"生成的视频文件为空或未成功创建: {output_path}")

            self.progress_signal.emit(f"剪切录屏完成 {current + 1}/{total}", current, total)

        except Exception as e:
            print(e, traceback.format_exc())
            self.progress_signal.emit(f"剪切录屏时出错: {str(e)}", current, total)

    def clip_serial_data(self, input_path, output_path, start_time, end_time, current, total):
        try:
            self.progress_signal.emit(f"开始剪切串口数据 {current + 1}/{total}", current, total)

            if not os.path.exists(input_path):
                raise FileNotFoundError(f"串口数据文件不存在: {input_path}")

            start_timestamp = pd.Timestamp(start_time).timestamp()
            end_timestamp = pd.Timestamp(end_time).timestamp()

            with open(input_path, 'r') as f:
                lines = f.readlines()

            clipped_lines = []
            for line in lines:
                try:
                    # 假设时间戳在每行的最前面，并且使用逗号分隔或空格分隔
                    parts = line.split(',')
                    if len(parts) == 0:
                        parts = line.split()
                    if len(parts) == 0:
                        continue
                    timestamp_str = parts[0]
                    timestamp = pd.Timestamp(timestamp_str).timestamp()
                    if start_timestamp <= timestamp <= end_timestamp:
                        clipped_lines.append(line)
                except Exception as e:
                    self.progress_signal.emit(f"解析行时出错: {line} - {str(e)}", current, total)
                    continue

            with open(output_path, 'w') as f:
                f.writelines(clipped_lines)

            self.progress_signal.emit(f"剪切串口数据完成 {current + 1}/{total}", current, total)

        except Exception as e:
            self.progress_signal.emit(f"剪切串口数据时出错: {str(e)}", current, total)

    def clip_imu_data(self, imu_data, issue_start_time, issue_end_time, output_path):
        time_list = list(imu_data.get("时间"))
        start_idx = 0
        end_idx = -1
        for i in range(len(time_list) - 1):
            if time_list[i] <= issue_start_time <= time_list[i + 1]:
                start_idx = i
            if time_list[i] <= issue_end_time <= time_list[i + 1]:
                end_idx = i

        result = dict()

        for key in imu_data.keys():
            result[key] = list(imu_data[key])[start_idx:end_idx]

        with open(os.path.join(output_path, 'imu_data.json'), 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=4)

        df = pd.DataFrame(result)
        df.to_csv(os.path.join(output_path, 'imu_data.csv'), encoding="utf-8")



# ------------------ 主程序入口 ------------------

if __name__ == "__main__":

    app = QApplication(sys.argv)

    # 使用 QAsyncioEventLoop，替换 Qt 的主事件循环
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.show()

    with loop:  # 上下文管理器自动清理
        loop.run_forever()


