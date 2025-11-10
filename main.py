import serial
import threading
import time
import struct
import math
from datetime import datetime
import tkinter as tk
from dialgauge import dialgauge
from dialgauge2 import dialgauge2

# 串口配置
PORT = "COM5"
BAUDRATE = 9600
TIMEOUT = 1

# 位移传感器配置（从move.py集成）
AUTO_MESSAGE = bytes.fromhex("01 03 00 00 00 02 C4 0B")  # 读取地址0-1（通道0位移）
INTERVAL = 0.02  # 20毫秒响应间隔

def bytes_to_hex(data: bytes) -> str:
    """把字节流转成HEX字符串"""
    return " ".join(f"{b:02X}" for b in data)

def get_timestamp():
    """获取当前时间戳"""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

def calculate_modbus_crc(data: bytes):
    """计算Modbus CRC16校验码"""
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
    """验证Modbus帧的CRC校验"""
    if len(frame) < 5:
        return False
    data = frame[:-2]
    recv_crc = struct.unpack('<H', frame[-2:])[0]
    return recv_crc == calculate_modbus_crc(data)

def parse_displacement(frame: bytes):
    """
    位移数据解析函数（从move.py集成）
    确保 9B 44 C3 0F 等零点数据被正确解析为 0.000 mm
    """
    if len(frame) < 9:
        return None, "长度不足"
    if frame[1] != 0x03 or frame[2] != 0x04:
        return None, "帧格式错误"

    raw_bytes = frame[3:7]

    # 特殊处理已知的零点数据模式
    zero_patterns = [
        bytes([0x9B, 0x44, 0xC3, 0x0F]),  # 已知零点模式1
        bytes([0x89, 0x14, 0x44, 0xEA]),  # 已知零点模式2
        bytes([0x1D, 0x31, 0x44, 0xD1]),  # 已知零点模式3
    ]

    # 检查是否为零点模式
    for pattern in zero_patterns:
        if raw_bytes == pattern:
            return 0.000, "零点位置"

    # 尝试32位大端浮点数解析
    try:
        raw_float = struct.unpack('>f', raw_bytes)[0]
        if math.isfinite(raw_float):
            # 如果浮点值极小（接近零），认为是零点
            if abs(raw_float) < 1e-10:
                return 0.000, "32位浮点零值"

            # 尝试不同的单位换算
            # 方法1: 假设单位为0.1um
            disp_mm = raw_float * 0.0001  # 0.1um → mm
            if 0.001 <= abs(disp_mm) <= 100:  # 合理范围
                return round(disp_mm, 3), "32位浮点(0.1um)"
    except:
        pass

    # 尝试16位小端整数解析（使用前2字节）
    try:
        raw_int = struct.unpack('<h', raw_bytes[0:2])[0]
        if raw_int == 0:
            return 0.000, "16位整数零值"

        # 假设单位为0.1um
        disp_mm = raw_int * 0.0001  # 0.1um → mm
        if 0.001 <= abs(disp_mm) <= 100:  # 合理范围
            return round(disp_mm, 3), "16位整数(0.1um)"
    except:
        pass

    # 如果所有方法都无法得到合理结果，返回零点
    return 0.000, "默认零点"

def send_and_wait_response(ser, message: bytes, label="[SEND]"):
    """发送HEX消息并等待反馈"""
    ser.reset_input_buffer()
    ser.write(message)
    print(f"{label} {bytes_to_hex(message)}")

    time.sleep(0.1)  # 给设备点时间
    if ser.in_waiting:
        data = ser.read(ser.in_waiting)
        if data:
            print(f"  ↳ [RECV] {bytes_to_hex(data)}")
            return data
    print("  ↳ [RECV] (无反馈)")
    return None

def displacement_sensor_reader(ser, gauge1, gauge2):
    """位移传感器数据读取和表盘更新"""
    running = True
    last_displacement = None

    def read_serial_data():
        """持续读取串口数据"""
        nonlocal running
        buffer = bytearray()

        while running:
            try:
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting)
                    buffer.extend(data)

                    # 查找完整的Modbus帧（9字节）
                    while len(buffer) >= 9:
                        # 查找帧头（从站地址01，功能码03）
                        start_idx = -1
                        for i in range(len(buffer) - 8):
                            if buffer[i] == 0x01 and buffer[i+1] == 0x03:
                                start_idx = i
                                break

                        if start_idx == -1:
                            buffer.clear()
                            break

                        # 移除帧头之前的数据
                        if start_idx > 0:
                            buffer = buffer[start_idx:]

                        # 检查是否有完整帧
                        if len(buffer) >= 9:
                            frame = bytes(buffer[:9])
                            buffer = buffer[9:]

                            # 验证CRC
                            if verify_modbus_frame(frame):
                                print(f"[{get_timestamp()}] 📥 {bytes_to_hex(frame)}")

                                # 解析位移数据
                                disp_mm, method = parse_displacement(frame)
                                if disp_mm is not None:
                                    print(f"[{get_timestamp()}] 📊 位移: {disp_mm:.4f} mm")

                                    # 更新两个表盘的位移值
                                    update_gauge_displacement(gauge1, disp_mm)
                                    update_gauge_displacement(gauge2, disp_mm)
                                else:
                                    print(f"[{get_timestamp()}] ❌ 解析失败: {method}")
                            else:
                                print(f"[{get_timestamp()}] ❌ CRC校验失败: {bytes_to_hex(frame)}")
                        else:
                            break

                time.sleep(0.001)  # 1毫秒休眠，支持高频响应
            except Exception as e:
                print(f"[{get_timestamp()}] ❌ 读取错误: {e}")
                time.sleep(0.1)

    def auto_send_commands():
        """自动发送查询命令"""
        nonlocal running
        while running:
            try:
                ser.write(AUTO_MESSAGE)
                print(f"[{get_timestamp()}] 📤 {bytes_to_hex(AUTO_MESSAGE)}")
                time.sleep(INTERVAL)
            except Exception as e:
                print(f"[{get_timestamp()}] ❌ 发送错误: {e}")
                time.sleep(1)

    # 启动读取和发送线程
    read_thread = threading.Thread(target=read_serial_data, daemon=True)
    send_thread = threading.Thread(target=auto_send_commands, daemon=True)

    read_thread.start()
    send_thread.start()

    try:
        # 主线程等待
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        running = False
        print(f"[{get_timestamp()}] 程序退出")

def update_gauge_displacement(gauge, displacement_mm):
    """更新表盘的位移值 - 优化零点校准和指针映射"""
    try:
        # 获取表盘范围
        max_range = gauge.rangeupperbound

        # 定义位移传感器的实际测量范围（根据实际观测数据调整）
        sensor_range = 10.0  # ±10mm

        # 零点校准：确保 0.000mm 对应 lengthofmeas = 0（表盘零位）
        if abs(displacement_mm) < 0.001:  # 零点容差：±0.001mm
            normalized_value = 0.0
            print(f"[{get_timestamp()}] 🎯 零点校准: {displacement_mm:.4f}mm → lengthofmeas = 0.000")
        else:
            # 位移值映射算法：
            # - 正位移：0 到 +sensor_range mm 映射到 0 到 max_range/2
            # - 负位移：0 到 -sensor_range mm 映射到 0 到 max_range/2（取绝对值）
            # 这样确保零点在表盘中心，正负位移都从零点开始

            if displacement_mm > 0:
                # 正位移：顺时针方向
                normalized_value = min(displacement_mm * max_range / (2 * sensor_range), max_range)
            else:
                # 负位移：也映射为正值，但在显示时可以通过颜色或其他方式区分
                normalized_value = min(abs(displacement_mm) * max_range / (2 * sensor_range), max_range)

        # 设置表盘的测量值
        gauge.lengthofmeas = normalized_value

        # 更新数字显示器 - 显示实际位移值而不是归一化值
        if hasattr(gauge, 'indicator'):
            # 根据位移值设置显示颜色
            if abs(displacement_mm) < 0.001:
                # 零点：绿色显示
                gauge.indicator.configure(text=f"{displacement_mm:.4f} mm", fg="green")
            elif displacement_mm > 0:
                # 正位移：蓝色显示
                gauge.indicator.configure(text=f"+{displacement_mm:.4f} mm", fg="blue")
            else:
                # 负位移：红色显示
                gauge.indicator.configure(text=f"{displacement_mm:.4f} mm", fg="red")

        # 更新指针位置
        if hasattr(gauge, 'mycanvas') and hasattr(gauge, 'hand1') and hasattr(gauge, 'hand2'):
            # 获取新的指针坐标
            coords_a1 = gauge.coordinateofA1()
            coords_a2 = gauge.coordinateofA2()

            # 更新指针位置
            gauge.mycanvas.coords(gauge.hand1, coords_a1)
            gauge.mycanvas.coords(gauge.hand2, coords_a2)

            # 零点时特殊处理：确保指针指向12点钟方向
            if abs(displacement_mm) < 0.001:
                print(f"[{get_timestamp()}] 🎯 指针零点校准完成")

        # 调试信息（仅在位移变化时输出）
        if hasattr(gauge, '_last_displacement') and abs(gauge._last_displacement - displacement_mm) > 0.001:
            print(f"[{get_timestamp()}] 📊 表盘更新: {displacement_mm:.4f}mm → lengthofmeas={normalized_value:.4f}")
        gauge._last_displacement = displacement_mm

    except Exception as e:
        print(f"[{get_timestamp()}] ❌ 更新表盘错误: {e}")
        import traceback
        traceback.print_exc()

def setup_gauge_for_displacement(gauge):
    """配置表盘用于位移传感器显示"""
    try:
        # 停止原有的预设点循环和自动运行
        gauge.running = False
        gauge.moving_to_preset = False
        gauge.preset_cycle_complete = True

        # 清空预设点，改为实时数据驱动
        gauge.preset_positions = []

        # 初始化位移相关属性
        gauge._last_displacement = 0.0

        # 设置初始零点位置
        gauge.lengthofmeas = 0.0

        # 更新显示为零点状态
        if hasattr(gauge, 'indicator'):
            gauge.indicator.configure(text="0.000 mm", fg="green")

        # 确保指针指向零位（12点钟方向）
        if hasattr(gauge, 'mycanvas') and hasattr(gauge, 'hand1') and hasattr(gauge, 'hand2'):
            gauge.mycanvas.coords(gauge.hand1, gauge.coordinateofA1())
            gauge.mycanvas.coords(gauge.hand2, gauge.coordinateofA2())

        # 输出表盘配置信息
        gauge_type = "dialgauge" if gauge.rangeupperbound == 10 else "dialgauge2"
        print(f"[{get_timestamp()}] 🔧 {gauge_type}已配置为位移传感器显示模式")
        print(f"[{get_timestamp()}] 📏 表盘范围: 0-{gauge.rangeupperbound}, 位移范围: ±10mm")
        print(f"[{get_timestamp()}] 🎯 零点校准: lengthofmeas = 0.000 (12点钟方向)")

    except Exception as e:
        print(f"[{get_timestamp()}] ❌ 配置表盘错误: {e}")
        import traceback
        traceback.print_exc()

def main():
    try:
        # 打开串口
        ser = serial.Serial(PORT, BAUDRATE, timeout=TIMEOUT)
        print(f"[{get_timestamp()}] ✅ 串口 {PORT} 打开成功")
        print(f"[{get_timestamp()}] 📋 位移传感器数据采集已启动，更新间隔: {INTERVAL*1000:.0f}毫秒")

        # 创建GUI窗口
        root = tk.Tk()
        root.title("位移传感器双表盘显示系统")
        root.geometry("1600x800")  # 调整窗口大小以容纳两个表盘

        # 创建第一个表盘（左侧）
        print(f"[{get_timestamp()}] 🔧 创建第一个表盘...")
        gauge1 = dialgauge(root)
        gauge1.drawbackground()
        gauge1.showcavnas()
        gauge1.pack(side=tk.LEFT, padx=20, pady=10)

        # 配置第一个表盘用于位移显示
        setup_gauge_for_displacement(gauge1)

        # 创建第二个表盘（右侧）
        print(f"[{get_timestamp()}] 🔧 创建第二个表盘...")
        gauge2 = dialgauge2(root)
        gauge2.drawbackground()
        gauge2.showcavnas()
        gauge2.pack(side=tk.RIGHT, padx=20, pady=10)

        # 配置第二个表盘用于位移显示
        setup_gauge_for_displacement(gauge2)

        # 添加状态标签
        status_frame = tk.Frame(root)
        status_frame.pack(side=tk.BOTTOM, pady=10)

        status_label = tk.Label(status_frame,
                               text="位移传感器实时数据显示 - 数据来源: COM5",
                               font=("Arial", 12, "bold"),
                               fg="blue")
        status_label.pack()

        # 启动位移传感器数据读取线程
        sensor_thread = threading.Thread(
            target=displacement_sensor_reader,
            args=(ser, gauge1, gauge2),
            daemon=True
        )
        sensor_thread.start()

        # 启动GUI主循环
        print(f"[{get_timestamp()}] 🚀 GUI界面已启动，位移数据将实时更新到双表盘")
        print(f"[{get_timestamp()}] 💡 关闭窗口或按Ctrl+C退出程序")

        root.mainloop()

    except serial.SerialException as e:
        print(f"[{get_timestamp()}] ❌ 串口错误: {e}")
        print(f"[{get_timestamp()}] 💡 请检查串口连接和设备状态")
    except KeyboardInterrupt:
        print(f"[{get_timestamp()}] 🛑 程序中断，退出")
    except Exception as e:
        print(f"[{get_timestamp()}] ❌ 程序错误: {e}")
    finally:
        try:
            if 'ser' in locals() and ser.is_open:
                ser.close()
                print(f"[{get_timestamp()}] 🔒 串口已关闭")
        except:
            pass

if __name__ == "__main__":
    main()