import serial
import threading
import time
import struct
import math
from datetime import datetime

PORT = "COM5"
BAUDRATE = 9600
INTERVAL = 0.02  # 20毫秒响应间隔
AUTO_ENABLE = True
# 根据图片，地址0-1是通道0位移值，地址2-3是通道1位移值
AUTO_MESSAGE = bytes.fromhex("01 03 00 00 00 02 C4 0B")  # 读取地址0-1（通道0位移）
# 备用命令：读取地址2-3（通道1位移）: "01 03 00 02 00 02 C4 38"

# 根据图片修正：单位是um，不是0.1um
# um → mm 的换算系数
UNIT_MM_FACTOR = 0.001

running = True
last_displacement = None


def get_timestamp():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def bytes_to_hex(data: bytes):
    return " ".join(f"{b:02X}" for b in data)


def calculate_modbus_crc(data: bytes):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def verify_modbus_frame(frame: bytes):
    if len(frame) < 5:
        return False
    data = frame[:-2]
    recv_crc = struct.unpack('<H', frame[-2:])[0]
    return recv_crc == calculate_modbus_crc(data)


def parse_displacement(frame: bytes):
    """
    位移数据解析（IEEE 754 浮点 + 字节序重排）
    - 帧格式: 01 03 04 <D0 D1 D2 D3> CRClo CRChi
    - 数据段4字节需重排: [D0,D1,D2,D3] -> [D2,D3,D0,D1]
    - 以IEEE 754大端序解析为32位浮点，单位为微米(um)
    - 转换为毫米(mm): um / 1000
    保持CRC校验和帧格式验证逻辑不变
    """
    if len(frame) < 9:
        return None, "长度不足"
    if frame[1] != 0x03 or frame[2] != 0x04:
        return None, "帧格式错误"

    data4 = frame[3:7]
    if len(data4) != 4:
        return None, "数据段长度错误"

    # 字节序转换: [B8,25,C2,99] -> [C2,99,B8,25]
    reordered = bytes([data4[2], data4[3], data4[0], data4[1]])

    try:
        value_um = struct.unpack('>f', reordered)[0]  # IEEE 754 Big-Endian
        if not math.isfinite(value_um):
            return None, "非有限值"
        value_mm = value_um / 1000.0  # um -> mm
        return value_mm, "IEEE754_BE_um->mm"
    except Exception as e:
        return None, f"解析异常: {e}"


def reader(ser):
    global running, last_displacement
    buffer = bytearray()
    while running:
        try:
            if ser.in_waiting:
                buffer.extend(ser.read(ser.in_waiting))
                while len(buffer) >= 9:
                    if buffer[0] != 0x01:
                        buffer.pop(0)
                        continue
                    frame = bytes(buffer[:9])
                    if verify_modbus_frame(frame):
                        buffer = buffer[9:]
                        print(f"[{get_timestamp()}] 📥 {bytes_to_hex(frame)}")
                        disp_mm, method = parse_displacement(frame)

                        if disp_mm is not None:
                            print(f"[{get_timestamp()}] 📊 位移: {disp_mm:.4f} mm")
                        else:
                            print(f"[{get_timestamp()}] ❌ 解析失败: {method}")
                    else:
                        buffer.pop(0)
            time.sleep(0.01)
        except Exception as e:
            print(f"[{get_timestamp()}] ❌ 读取错误: {e}")
            time.sleep(0.1)


def auto_sender(ser):
    global running
    while running:
        try:
            ser.write(AUTO_MESSAGE)
            print(f"[{get_timestamp()}] 📤 {bytes_to_hex(AUTO_MESSAGE)}")
        except Exception as e:
            print(f"[{get_timestamp()}] ❌ 发送错误: {e}")
        time.sleep(INTERVAL)


def main():
    global running
    try:
        ser = serial.Serial(PORT, BAUDRATE, timeout=0.1)
        print(f"[{get_timestamp()}] ✅ 串口 {PORT} 打开成功")

        t1 = threading.Thread(target=reader, args=(ser,), daemon=True)
        t1.start()
        if AUTO_ENABLE:
            t2 = threading.Thread(target=auto_sender, args=(ser,), daemon=True)
            t2.start()

        while True:
            cmd = input("输入 exit 退出: ").strip().lower()
            if cmd in ["exit", "quit"]:
                running = False
                break
    except Exception as e:
        print(f"❌ 串口错误: {e}")


if __name__ == "__main__":
    main()
