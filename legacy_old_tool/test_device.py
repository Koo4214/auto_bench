import asyncio
import time
import json
import traceback

import pandas as pd
import os

import bleak
import device_model

# 扫描到的设备 Scanned devices
devices = []
# 蓝牙设备 BLEDevice
BLEDevice = None


# 扫描蓝牙设备并过滤名称
# Scan Bluetooth devices and filter names
async def scan():
    global devices
    global BLEDevice
    find = []
    print("Searching for Bluetooth devices......")
    try:
        loop = asyncio.get_event_loop()
        devices = await bleak.BleakScanner.discover(timeout=20.0)
        print("Search ended")
        for d in devices:
            if d.name is not None and "WT" in d.name:
                print(d.address)
                BLEDevice = d
        # if len(find) == 0:
        #     print("No devices found in this search!")
        # else:
        #     user_input = input("Please enter the Mac address you want to connect to (e.g. DF:E9:1F:2C:BD:59)：")
        #     for d in devices:
        #         if d.address == user_input:
        #             BLEDevice = d
        #             break
    except Exception as ex:
        print("Bluetooth search failed to start")
        print(ex)


# 指定MAC地址搜索并连接设备
# Specify MAC address to search and connect devices
async def scanByMac(device_mac):
    global BLEDevice
    print("Searching for Bluetooth devices......")
    BLEDevice = await bleak.BleakScanner.find_device_by_address(device_mac, timeout=20)


# 数据更新时会调用此方法 This method will be called when data is updated
def updateData(DeviceModel):
    # 直接打印出设备数据字典 Directly print out the device data dictionary
    print(DeviceModel.deviceData)
    # print(111)
    # 获得X轴加速度 Obtain X-axis acceleration
    # print(DeviceModel.get("AccX"))

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

    return modified_data

class Test:
    def __init__(self, save_dir):
        super().__init__()
        self.save_dir = save_dir
        self.is_recording = False
        self.BLE_device = None
        asyncio.run(self.scan())
        self.device = device_model.DeviceModel("MyBle5.0", self.BLE_device, self.update_data)
        self.data = dict()

    # 数据更新时会调用此方法 This method will be called when data is updated
    def update_data(self, device_model):
        data_info = device_model.deviceData
        modified_data = modify_data(data_info)
        print(data_info)
        for key in modified_data:
            if key in self.data:
                self.data[key].append(modified_data[key])
            else:
                self.data[key] = [modified_data[key]]

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
                    print(d.address)
                    self.BLE_device = d
        except Exception as ex:
            print("Bluetooth search failed to start")
            print(traceback.format_exc())

    def store_data(self):
        json_file = os.path.join(self.save_dir, "imu_data.json")
        csv_file = os.path.join(self.save_dir, "imu_data.csv")

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

        df = pd.DataFrame(self.data)
        df.to_csv(csv_file)

    def run(self):
        asyncio.run(self.device.openDevice())

    def stop(self):
        self.device.closeDevice()
        self.store_data()

if __name__ == '__main__':
    # # 方式一：广播搜索和连接蓝牙设备
    # # Method 1:Broadcast search and connect Bluetooth devices
    # asyncio.run(scan())
    #
    # # # 方式二：指定MAC地址搜索并连接设备
    # # # Method 2: Specify MAC address to search and connect devices
    # # asyncio.run(scanByMac("C6:46:21:41:0B:BD"))
    #
    # if BLEDevice is not None:
    #     # 创建设备 Create device
    #     device = device_model.DeviceModel("MyBle5.0", BLEDevice, updateData)
    #     # 开始连接设备 Start connecting devices
    #     asyncio.run(device.openDevice())
    #
    # else:
    #     print("This BLEDevice was not found!!")

    test = Test(r"C:\Users\Leslie\PycharmProjects\benchmark_test\test_run")
    test.run()
    time.sleep(30)
    test.stop()
