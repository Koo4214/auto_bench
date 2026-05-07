# coding: UTF-8
import asyncio
import bleak
import struct
import threading
import time

TARGET_SERVICE_UUID = "0000ffe5-0000-1000-8000-00805f9a34fb"
TARGET_CHARACTERISTIC_UUID_READ = "0000ffe4-0000-1000-8000-00805f9a34fb"
TARGET_CHARACTERISTIC_UUID_WRITE = "0000ffe9-0000-1000-8000-00805f9a34fb"


def _normalize_uuid(value):
    if value is None:
        return ""
    return str(value).strip().lower()


class DeviceModel:
    deviceName = "我的设备"
    deviceData = {}
    isOpen = False
    TempBytes = []

    def __init__(self, deviceName, BLEDevice, callback_method):
        print("Initialize device model")
        self.deviceName = deviceName
        self.BLEDevice = BLEDevice
        self.client = None
        self.writer_characteristic = None
        self.isOpen = False
        self.callback_method = callback_method
        self.deviceData = {}

    def set(self, key, value):
        self.deviceData[key] = value

    def get(self, key):
        if key in self.deviceData:
            return self.deviceData[key]
        return None

    def remove(self, key):
        del self.deviceData[key]

    async def openDevice(self):
        print("Opening device......")
        async with bleak.BleakClient(self.BLEDevice, timeout=15) as client:
            self.client = client
            self.isOpen = True
            notify_characteristic = None

            print("Matching services......")
            for service in client.services:
                if _normalize_uuid(service.uuid) == TARGET_SERVICE_UUID:
                    print(f"Service: {service}")
                    print("Matching characteristic......")
                    for characteristic in service.characteristics:
                        normalized_uuid = _normalize_uuid(characteristic.uuid)
                        if normalized_uuid == TARGET_CHARACTERISTIC_UUID_READ:
                            notify_characteristic = characteristic
                        if normalized_uuid == TARGET_CHARACTERISTIC_UUID_WRITE:
                            self.writer_characteristic = characteristic
                    if notify_characteristic:
                        break

            if self.writer_characteristic:
                print("Reading magnetic field quaternions")
                await asyncio.sleep(3)
                asyncio.create_task(self.sendDataTh())

            if notify_characteristic:
                print(f"Characteristic: {notify_characteristic}")
                try:
                    await client.start_notify(notify_characteristic.uuid, self.onDataReceived)
                except Exception as exc:
                    raise RuntimeError(f"WT901 BLE 通知启动失败: {exc}") from exc

                try:
                    while self.isOpen:
                        await asyncio.sleep(1)
                except asyncio.CancelledError:
                    pass
                finally:
                    await client.stop_notify(notify_characteristic.uuid)
            else:
                available_services = ", ".join(_normalize_uuid(service.uuid) for service in client.services) or "<none>"
                raise RuntimeError(
                    "BLE 服务与 WT901 协议不兼容；"
                    f"需要服务 {TARGET_SERVICE_UUID} 和通知特征 {TARGET_CHARACTERISTIC_UUID_READ}，"
                    f"当前服务: {available_services}"
                )

    def closeDevice(self):
        self.isOpen = False
        print("The device is turned off")

    async def sendDataTh(self):
        while self.isOpen:
            await self.readReg(0x3A)
            await asyncio.sleep(0.1)
            await self.readReg(0x51)
            await asyncio.sleep(0.1)

    def onDataReceived(self, sender, data):
        tempdata = bytes.fromhex(data.hex())
        for var in tempdata:
            self.TempBytes.append(var)
            if len(self.TempBytes) == 1 and self.TempBytes[0] != 0x55:
                del self.TempBytes[0]
                continue
            if len(self.TempBytes) == 2 and (self.TempBytes[1] != 0x61 and self.TempBytes[1] != 0x71):
                del self.TempBytes[0]
                continue
            if len(self.TempBytes) == 20:
                self.processData(self.TempBytes)
                self.TempBytes.clear()

    def processData(self, Bytes):
        if Bytes[1] == 0x61:
            Ax = self.getSignInt16(Bytes[3] << 8 | Bytes[2]) / 32768 * 16
            Ay = self.getSignInt16(Bytes[5] << 8 | Bytes[4]) / 32768 * 16
            Az = self.getSignInt16(Bytes[7] << 8 | Bytes[6]) / 32768 * 16
            Gx = self.getSignInt16(Bytes[9] << 8 | Bytes[8]) / 32768 * 2000
            Gy = self.getSignInt16(Bytes[11] << 8 | Bytes[10]) / 32768 * 2000
            Gz = self.getSignInt16(Bytes[13] << 8 | Bytes[12]) / 32768 * 2000
            AngX = self.getSignInt16(Bytes[15] << 8 | Bytes[14]) / 32768 * 180
            AngY = self.getSignInt16(Bytes[17] << 8 | Bytes[16]) / 32768 * 180
            AngZ = self.getSignInt16(Bytes[19] << 8 | Bytes[18]) / 32768 * 180
            self.set("AccX", round(Ax, 3))
            self.set("AccY", round(Ay, 3))
            self.set("AccZ", round(Az, 3))
            self.set("AsX", round(Gx, 3))
            self.set("AsY", round(Gy, 3))
            self.set("AsZ", round(Gz, 3))
            self.set("AngX", round(AngX, 3))
            self.set("AngY", round(AngY, 3))
            self.set("AngZ", round(AngZ, 3))
            self.callback_method(self)
        else:
            if Bytes[2] == 0x3A:
                Hx = self.getSignInt16(Bytes[5] << 8 | Bytes[4]) / 120
                Hy = self.getSignInt16(Bytes[7] << 8 | Bytes[6]) / 120
                Hz = self.getSignInt16(Bytes[9] << 8 | Bytes[8]) / 120
                self.set("HX", round(Hx, 3))
                self.set("HY", round(Hy, 3))
                self.set("HZ", round(Hz, 3))
            elif Bytes[2] == 0x51:
                Q0 = self.getSignInt16(Bytes[5] << 8 | Bytes[4]) / 32768
                Q1 = self.getSignInt16(Bytes[7] << 8 | Bytes[6]) / 32768
                Q2 = self.getSignInt16(Bytes[9] << 8 | Bytes[8]) / 32768
                Q3 = self.getSignInt16(Bytes[11] << 8 | Bytes[10]) / 32768
                self.set("Q0", round(Q0, 5))
                self.set("Q1", round(Q1, 5))
                self.set("Q2", round(Q2, 5))
                self.set("Q3", round(Q3, 5))

    @staticmethod
    def getSignInt16(num):
        if num >= pow(2, 15):
            num -= pow(2, 16)
        return num

    async def sendData(self, data):
        try:
            if self.client.is_connected and self.writer_characteristic is not None:
                await self.client.write_gatt_char(self.writer_characteristic.uuid, bytes(data))
        except Exception as ex:
            print(ex)

    async def readReg(self, regAddr):
        await self.sendData(self.get_readBytes(regAddr))

    async def writeReg(self, regAddr, sValue):
        self.unlock()
        await asyncio.sleep(0.1)
        await self.sendData(self.get_writeBytes(regAddr, sValue))
        await asyncio.sleep(0.1)
        self.save()

    @staticmethod
    def get_readBytes(regAddr):
        tempBytes = [None] * 5
        tempBytes[0] = 0xff
        tempBytes[1] = 0xaa
        tempBytes[2] = 0x27
        tempBytes[3] = regAddr
        tempBytes[4] = 0
        return tempBytes

    @staticmethod
    def get_writeBytes(regAddr, rValue):
        tempBytes = [None] * 5
        tempBytes[0] = 0xff
        tempBytes[1] = 0xaa
        tempBytes[2] = regAddr
        tempBytes[3] = rValue & 0xff
        tempBytes[4] = rValue >> 8
        return tempBytes

    def unlock(self):
        cmd = self.get_writeBytes(0x69, 0xB588)
        self.sendData(cmd)

    def save(self):
        cmd = self.get_writeBytes(0x00, 0x0000)
        self.sendData(cmd)
