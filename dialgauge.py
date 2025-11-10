import time
import random
import tkinter as tk
import math as mt
import csv
from datetime import datetime
from tkinter import messagebox
import sys, locale
try:
    # 统一控制台编码，修复中文输出乱码（在支持reconfigure的Python上生效）
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass
try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
# 抗锯齿绘制（可选）
try:
    import aggdraw
    AGGDRAW_AVAILABLE = True
except Exception:
    AGGDRAW_AVAILABLE = False
# 传感器依赖与move.py复用
import threading
try:
    import serial
except Exception:
    serial = None
try:
    from move import (
        PORT as _MV_PORT,
        BAUDRATE as _MV_BAUD,
        INTERVAL as _MV_INTERVAL,
        AUTO_MESSAGE as _MV_MSG,
        parse_displacement as _mv_parse,
        verify_modbus_frame as _mv_verify,
        get_timestamp as _mv_ts,
        bytes_to_hex as _mv_hex,
    )
except Exception:
    _MV_PORT = "COM5"
    _MV_BAUD = 9600
    _MV_INTERVAL = 0.02
    _MV_MSG = bytes.fromhex("01 03 00 00 00 02 C4 0B")
    import struct
    def _mv_hex(data: bytes):
        return " ".join(f"{b:02X}" for b in data)
    def _mv_ts():
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]
    def _calc_crc(data: bytes):
        crc = 0xFFFF
        for b in data:
            crc ^= b
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc
    def _mv_verify(frame: bytes):
        if len(frame) < 5:
            return False
        data = frame[:-2]
        recv_crc = struct.unpack('<H', frame[-2:])[0]
        return recv_crc == _calc_crc(data)
    def _mv_parse(frame: bytes):
        # IEEE754 + 字节序重排: [D0,D1,D2,D3] -> [D2,D3,D0,D1], 然后以大端浮点解析为um，再换算为mm
        if len(frame) < 9 or frame[1]!=0x03 or frame[2]!=0x04:
            return None, "格式"
        data4 = frame[3:7]
        if len(data4) != 4:
            return None, "长度"
        reordered = bytes([data4[2], data4[3], data4[0], data4[1]])
        try:
            val_um = struct.unpack('>f', reordered)[0]
            import math
            if not math.isfinite(val_um):
                return None, "非数"
            disp_mm = val_um / 1000.0
            return disp_mm, "IEEE754_BE_um->mm"
        except Exception as e:
            return None, f"异常:{e}"
        except Exception:
            pass
        return 0.0, "默认"


class dialgauge(tk.Frame):
    def __init__(self,master=None):
        super().__init__(master)


        self.running = False
        self.lengthofmeas=float(0) #the initial length of measurand
        self.increaseinterval=0.005  #增加步长以提供更平滑的移动
        self.phasedelaytozero=0.5*mt.pi #define a phase delay to set number 0 at top center pi/2
        # 全局缩放：将基准800像素的表盘等比例缩放到500像素
        self.canvaslength=500       # the length of canvas (square dial region width/height)
        self.canvaswidth=self.canvaslength # the width of canvas
        self.ui_scale = self.canvaslength / 800.0  # scale factor relative to 800
        # 画布向下扩展用于放置按钮/滑块/状态（不改变表盘区域）
        self.control_panel_height = int(240 * self.ui_scale)
        self.canvasheight = self.canvaslength + self.control_panel_height
        self.centerx=self.canvaslength/2 # x center remains in the dial square region
        self.centery=self.canvaslength/2 # y center pinned to dial square region (not total height)
        self.movelengthofA2center=self.canvaslength/10 #the distantce of center of A2 to center of canvas
        self.centerofarmA2x=self.centerx-self.movelengthofA2center # the x of center coordinate of A2
        self.centerofarmA2y=self.centery+self.movelengthofA2center # the y of center coordinate of A2
        # 固定像素：主表盘半径、A1指针圆端半径、副表盘半径（相对基准800像素缩放）
        self.radiusofdialA1=int(400 * self.ui_scale)
        self.radiusofcircleofhand1=int(24 * self.ui_scale)
        self.radiusfdialA2=int(80 * self.ui_scale)
        # 位移传感器监控相关
        self.sensor_threshold = 0.01  # mm
        self._sensor_started = False
        self._sensor_ser = None
        self._sensor_threads = []
        self._sensor_last_value = None
        self._sensor_lock = threading.Lock()
        self._sensor_status_var = None  # 在打开预设窗口时创建
        self._sensor_value_var = None   # 在打开预设窗口时创建

        # 两阶段检测参数与状态
        self.still_threshold = 0.003  # mm 静止判定阈值
        self.still_confirm_count = 5  # 连续N次小于静止阈值
        self._det_status_var = None   # 检测状态显示变量
        self._sensor_state = 'idle'   # idle/await_still/await_change
        self._sensor_prev_value = None
        self._sensor_still_count = 0
        self._sensor_baseline = None

        self.radiusofcircleofhand2=int(13 * self.ui_scale)
        self.widthoftickA1=2 # the width of tick mark of dial A1
        self.widthofdialA2=max(1, int(6 * self.ui_scale)) # the width of boundary of dial A2
        self.widthoftickA2=2 # the width of tick mar of dial A2
        self.neftickmarkl= self.radiusofdialA1-int(70 * self.ui_scale) # the length from the near end of long tick mark to center of canvas
        self.feftickmarkl= self.radiusofdialA1-int(5 * self.ui_scale) # the length from the far end of long tick mark to center of canvas
        self.neftickmarkm= self.radiusofdialA1-int(60 * self.ui_scale) # the length from the near end of middle tick mark to center of canvas
        self.feftickmarkm=self.feftickmarkl # the lenght from the far end of middle tick mark to center of canvas
        self.phasedelayoftickmarkm=mt.pi*0.1 #the phase delay to set the middle tick start from the 0.1*pi from line of top center
        self.neftickmarks= self.radiusofdialA1-int(50 * self.ui_scale) # the length from the near end of short tick mark to center of canvas
        self.feftickmarks=self.feftickmarkl #define the length from the far end of short tickmark to center of canvas
        self.lengthofnumber=self.neftickmarkl-int(30 * self.ui_scale) # the length from number to center of canvas
        self.phasedelaytozero=0.5*mt.pi #define a phase delay to set number 0 at top center pi/2
        self.neftickmarkA2=self.radiusfdialA2-int(10 * self.ui_scale) # the length from the near end of tick mark A2 to center of dial A2
        self.feftickmarkA2=self.radiusfdialA2-int(2 * self.ui_scale) # the length from the far end of tick mark A2 to center of dial A2
        self.lengthofnumberA2=self.neftickmarkA2-int(8 * self.ui_scale) # the length from number of A2 to center of center of A2
        self.numberofintervaloftickl=10 # the number of interval of long tick mark of A1
        self.numberofintervaloftickm=self.numberofintervaloftickl # the number of interval of middle tick mark of A1
        self.numberofintervalofticks=100 # the number of interval of short tick mark of A1
        self.numberofintervaloftickofA2=self.numberofintervaloftickl # the number of interval of tick mark of A2
        self.strofA1=(0,10,20,30,40,50,60,70,80,90)
        self.strofA2=(0,1,2,3,4,5,6,7,8,9)
        self.intervaloftickl=1/self.numberofintervaloftickl # the interval of long tick mark
        self.intervaloftickm=1/self.numberofintervaloftickm # the interval of middle tick mark
        self.intervalofticks=1/self.numberofintervalofticks # the interval of short tick mark
        self.intervaloftickofA2=1/self.numberofintervaloftickofA2 # the interval of tick mark of A2
        self.mycanvas=tk.Canvas(self,width=self.canvaslength,height=self.canvasheight,bg="black")   #create a canvas
        self.rangeupperbound=10
        self.phasedelaytozero=0.5*mt.pi #define a phase delay to set number 0 at top center pi/2
############################################################################################################################
        # 时间间隔控制系统说明：
        # timeinterval: 控制指针更新频率的基础时间间隔（毫秒）
        # - 这个值决定了每次指针位置更新之间的时间间隔
        # - 较小的值（如10ms）提供更平滑的动画，但消耗更多CPU资源
        # - 较大的值（如50ms）降低CPU使用，但动画可能显得不够流畅
        # - 与pauseduration[0]配合使用，实现动态速度控制
        self.timeinterval=10 #基础更新间隔：10毫秒提供流畅的60FPS动画效果
        self.pausenumber=0 #暂停计数器：用于控制特定位置的暂停行为

        # 历史数据记录 - 仅记录预设点到达事件
        self.history_data = []  # 存储历史数据：(序号, 预设点值, 到达时间戳)
        self.preset_counter = 0   # 预设点到达计数器
        self.last_reached_preset = None  # 上次到达的预设点，避免重复记录

        # 镜像状态
        self.is_mirrored = False  # 镜像状态标志

        # 指针显示控制
        self.pointers_visible = True  # 指针可见性标志
        self.pointers_visible_before_preset = True  # 预设点暂停前的指针状态

        # 横向安装倾角模拟（±5°）
        self.horizontal_tilt_angle = 0.0
        self._tilt_scale_x = 1.0
        self._tilt_shift_x = 0.0
        self._tilt_window = None
        self._tilt_var = None

        # 性能优化缓存
        self.last_indicator_text = ""  # 缓存指示器文本，避免重复更新
        self._display_value = float(self.lengthofmeas)  # 数字指示平滑值

        # 预设位置跳转控制 - 改为用户可自定义
        self.preset_positions = [0.0,0.2,0.92,0.3,0.5,0.0,0.0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,1.1,1,0.9,0.8,0.7,0.6,0.5,0.4,0.3,0.2,0.1,0]  # 默认预设位置
        self.current_position_index = 0  # 当前位置索引
        self.jump_mode = False  # 跳转模式标志
        # 移除continuous_mode，始终使用连续移动模式
        self.pause_at_presets = True  # 在预设点暂停
        self.pause_duration = 1000  # 暂停时长(毫秒)
        self.moving_to_preset = False  # 是否正在移动到预设点
        self.target_preset = None  # 目标预设点
        self.target_preset_index = 0  # 目标预设点索引
        self.preset_cycle_complete = False  # 预设点循环是否完成
        # 触发模式：'time' 时间触发，'displacement' 位移变化触发
        self.trigger_mode = 'time'


        # 速度和暂停控制系统详解：
        # pauseduration[0]: 动态速度控制参数（毫秒）
        # - 这是用户通过速度滑块控制的实际时间间隔
        # - 范围：0.5-100毫秒，控制指针移动的实际速度
        # - 与timeinterval配合：timeinterval控制更新频率，pauseduration[0]控制移动速度
        # pauseduration[1]: 预设点暂停时长（毫秒）
        # - 指针到达预设位置时的暂停时间
        self.lengthtopause=(0.100,0.200) # 暂停触发位置：指针到达特定位置时暂停
        self.pauseduration=[1,1000] # [移动速度间隔(ms), 预设点暂停时长(ms)]
        self.gaugewaitingduration=1  # 等待状态的检查间隔
        self.numberofpiecewise=1     # 分段控制参数
############################################################################################################################
        # 美化的指示器
        self.indicator=tk.Label(self,text=str(self.lengthofmeas),
                               font=("Arial", 12, "bold"),width=12,
                               bg="#f0f0f0",fg="#333333",
                               relief=tk.RAISED,bd=2) #create a label to show the value of measurement

        # 美化的按钮样式
        button_style = {
            "font": ("Arial", 10, "bold"),
            "width": 10,
            "relief": tk.RAISED,
            "bd": 2,
            "bg": "#e6e6e6",
            "activebackground": "#d0d0d0"
        }

        self.mystart=tk.Button(self,text="▶ Start",command=self.start,**button_style)
        self.mystart.config(bg="#90EE90", activebackground="#7FDD7F")  # 绿色

        self.mystop=tk.Button(self,text="⏸ Stop",command=self.stop,**button_style)
        self.mystop.config(bg="#FFB6C1", activebackground="#FF9FAB")   # 粉色

        self.myreset=tk.Button(self,text="🔄 Reset",command=self.reset,**button_style)
        self.myreset.config(bg="#87CEEB", activebackground="#7BB8D6")  # 天蓝色


        # 美化的速度控制滑块（确保只创建一份，不重复）
        self.speed_label=tk.Label(self,text="⚡ Speed Control:",
                                 font=("Arial", 10, "bold"),
                                 bg="#f0f0f0",fg="#333333")
        self.speed_scale=tk.Scale(self, from_=1, to=200, orient=tk.HORIZONTAL, length=int(200*self.ui_scale),
                                 command=self.update_speed, label="Speed (ms/step)",
                                 font=("Arial", 9),
                                 bg="#f0f0f0",fg="#333333",
                                 troughcolor="#d0d0d0",
                                 activebackground="#4CAF50",
                                 resolution=1)  # 精确到1毫秒
        self.speed_scale.set(50)  # 默认速度设为中等（50毫秒间隔）

        # 美化的历史输出按钮
        self.history_button=tk.Button(self,text="📊 History",command=self.show_history,**button_style)
        self.history_button.config(bg="#DDA0DD", activebackground="#D18FD1")  # 紫色

        # 美化的镜像按钮
        self.mirror_button=tk.Button(self,text="🔄 Mirror",command=self.toggle_mirror,**button_style)
        self.mirror_button.config(bg="#F0E68C", activebackground="#E6DA7A")   # 卡其色

        # 指针显示控制按钮
        self.pointer_toggle_button=tk.Button(self,text="👁 Hide Pointers",command=self.toggle_pointers,**button_style)
        self.pointer_toggle_button.config(bg="#FFB6C1", activebackground="#FF91A4")  # 浅粉色

        # 预设位置管理组件
        self.preset_button=tk.Button(self,text="⚙ Presets",command=self.open_preset_manager,**button_style)
        self.preset_button.config(bg="#87CEEB", activebackground="#7BB8D6")  # 天蓝色

        # 横向倾角调节按钮
        self.horizontal_tilt_button = tk.Button(
            self,
            text="↔ 横向倾角 0.0°",
            command=self.open_horizontal_tilt_dialog,
            **button_style
        )
        self.horizontal_tilt_button.config(bg="#FFE4B5", activebackground="#F5D19C")
        self._update_horizontal_tilt_button_label()
        self._update_tilt_params()

        self.position_label=tk.Label(self,text="📍 Status:",
                                    font=("Arial", 10, "bold"),
                                    bg="#f0f0f0",fg="#333333")
        self.position_info=tk.Label(self,text=f"Mode: Continuous",
                                   font=("Arial", 9),
                                   bg="#f0f0f0",fg="#666666")

        # 添加详细状态显示
        self.status_detail_label=tk.Label(self,text="Ready to start",
                                         font=("Arial", 8),
                                         bg="#f0f0f0",fg="#888888")

        # 缺陷相关设置：指针颜色、中心偏移、缺失刻线集合
        self.pointer_color = "red"
        self.center_offset_enabled = False
        self.center_offset_dx = int(10*self.ui_scale)
        self.center_offset_dy = int(10*self.ui_scale)
        # 去除缺失刻线功能：不再维护对应集合

        # 优化的布局 - 创建更美观且对称的按钮排列
        self.indicatorwindow=self.mycanvas.create_window(int(400*self.ui_scale),int(580*self.ui_scale),window=self.indicator)

        # 以画布中心为轴的三行对称排布
        _py0 = int(self.canvaslength + 20*self.ui_scale)  # 面板顶部基线
        _cx = int(self.centerx)
        _dx = int(120*self.ui_scale)  # 水平间距

        # 第一行：Start / Stop / Reset（关于中心对称）
        self.mystartwindow=self.mycanvas.create_window(_cx-_dx, _py0 + int(30*self.ui_scale), window=self.mystart)
        self.mystopwindow=self.mycanvas.create_window(_cx,      _py0 + int(30*self.ui_scale), window=self.mystop)
        self.myresetwindow=self.mycanvas.create_window(_cx+_dx, _py0 + int(30*self.ui_scale), window=self.myreset)

        # 第二行：History / Mirror / PointerToggle（关于中心对称）
        self.history_button_window=self.mycanvas.create_window(_cx-_dx, _py0 + int(80*self.ui_scale), window=self.history_button)
        self.mirror_button_window=self.mycanvas.create_window(_cx,      _py0 + int(80*self.ui_scale), window=self.mirror_button)
        self.pointer_toggle_button_window=self.mycanvas.create_window(_cx+_dx, _py0 + int(80*self.ui_scale), window=self.pointer_toggle_button)

        # 第三行：CenterOffset / Mask / Continue（关于中心对称）
        self.defect_center_button=tk.Button(self,text="⚠ Center Offset",command=self.toggle_center_offset,**button_style)
        self.defect_center_button.config(bg="#FFA07A", activebackground="#FF8C69")
        self.defect_center_button_window=self.mycanvas.create_window(_cx-_dx, _py0 + int(130*self.ui_scale), window=self.defect_center_button)

        self.mask_button=tk.Button(self,text="▦ Mask",command=self.add_mask_box,**button_style)
        self.mask_button.config(bg="#EEE8AA", activebackground="#E6DD8A")
        self.mask_button_window=self.mycanvas.create_window(_cx,      _py0 + int(130*self.ui_scale), window=self.mask_button)
        self._mask_items=[]

        self.disp_continue_btn=tk.Button(self,text="▶ Continue",command=self.notify_displacement_change,**button_style)
        self.disp_continue_btn.config(bg="#ADD8E6", activebackground="#9AC7D7")
        self.disp_continue_window=self.mycanvas.create_window(_cx+_dx, _py0 + int(130*self.ui_scale), window=self.disp_continue_btn)
        # 初始隐藏
        self.mycanvas.coords(self.disp_continue_window, -1200, -1200)

        # 速度与状态控件移至按钮行下方，避免重叠
        below_y = _py0 + int(170*self.ui_scale)
        self.speed_label_window=self.mycanvas.create_window(int(120*self.ui_scale), below_y + int(0*self.ui_scale), window=self.speed_label)
        self.speed_scale_window=self.mycanvas.create_window(int(120*self.ui_scale), below_y + int(20*self.ui_scale), window=self.speed_scale)

        self.preset_button_window=self.mycanvas.create_window(int(520*self.ui_scale), below_y + int(20*self.ui_scale), window=self.preset_button)
        self.horizontal_tilt_button_window=self.mycanvas.create_window(
            int(520*self.ui_scale),
            below_y + int(60*self.ui_scale),
            window=self.horizontal_tilt_button
        )
        self.position_label_window=self.mycanvas.create_window(int(520*self.ui_scale), below_y + int(0*self.ui_scale), window=self.position_label)
        self.position_info_window=self.mycanvas.create_window(int(520*self.ui_scale), below_y + int(15*self.ui_scale), window=self.position_info)
        self.status_detail_window=self.mycanvas.create_window(int(520*self.ui_scale), below_y + int(35*self.ui_scale), window=self.status_detail_label)
        #self.mycanvas.create_window(480,650,window=self.quitmybotton) #put the button on the canvas
        # 统一做一次以中心为轴的等间距排布，保证对称且不重叠
        try:
            self._layout_buttons_centered()
        except Exception:
            pass
        
    def showcavnas(self):
        self.pack()
        self.mycanvas.pack()
        #self.quitmybotton.pack(side="bottom"and"right")
        #self.mystop.pack(side="bottom"and"right")
        #self.mystart.pack(side="bottom"and"right")
        #self.indicator.pack(side="bottom",fill="x")

    def create_mirrored_text(self, x, y, text, font_spec, **kwargs):
        """创建镜像文字，如果PIL可用则创建真正的镜像效果，否则使用普通文字"""
        # 处理标签，统一加入 dial_static 方便批量刷新
        tags = kwargs.pop("tags", ())
        if isinstance(tags, str):
            tags = (tags,)
        elif isinstance(tags, (list, tuple, set)):
            tags = tuple(tags)
        else:
            tags = ()
        if "dial_static" not in tags:
            tags = tuple(list(tags) + ["dial_static"])
        kwargs["tags"] = tags

        tx, ty = self._apply_tilt_to_point(x, y)

        if self.is_mirrored and PIL_AVAILABLE:
            try:
                font_family, font_size = font_spec[0], font_spec[1]
                if len(font_spec) > 2:
                    font_weight = font_spec[2]
                else:
                    font_weight = "normal"

                try:
                    if font_weight == "bold":
                        pil_font = ImageFont.truetype("arial.ttf", font_size)
                    else:
                        pil_font = ImageFont.truetype("arial.ttf", font_size)
                except Exception:
                    pil_font = ImageFont.load_default()

                # 获取文字边界框
                temp_img = Image.new('RGBA', (100, 100), (255, 255, 255, 0))
                temp_draw = ImageDraw.Draw(temp_img)
                bbox = temp_draw.textbbox((0, 0), text, font=pil_font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]

                # 创建文字图像并镜像
                text_img = Image.new('RGBA', (text_width + 10, text_height + 10), (255, 255, 255, 0))
                text_draw = ImageDraw.Draw(text_img)
                text_draw.text((5, 5), text, font=pil_font, fill='black')
                mirrored_img = text_img.transpose(Image.FLIP_LEFT_RIGHT)

                photo = ImageTk.PhotoImage(mirrored_img)
                if not hasattr(self, '_mirrored_images'):
                    self._mirrored_images = []
                self._mirrored_images.append(photo)
                return self.mycanvas.create_image(tx, ty, image=photo, **kwargs)
            except Exception as e:
                print(f"镜像文字创建失败: {e}")
                return self.mycanvas.create_text(tx, ty, text=text, font=font_spec, **kwargs)
        else:
            return self.mycanvas.create_text(tx, ty, text=text, font=font_spec, **kwargs)

    def _is_tilt_active(self):
        try:
            return abs(float(getattr(self, 'horizontal_tilt_angle', 0.0))) > 1e-4
        except Exception:
            return False

    def _update_tilt_params(self):
        angle = float(getattr(self, 'horizontal_tilt_angle', 0.0))
        angle = max(-5.0, min(5.0, angle))
        magnitude = abs(angle) / 5.0
        scale = 1.0 - 0.25 * magnitude
        self._tilt_scale_x = max(0.6, scale)
        self._tilt_shift_x = self.radiusofdialA1 * 0.2 * mt.sin(mt.radians(angle))

    def _apply_tilt_to_point(self, x, y):
        if not self._is_tilt_active():
            return (x, y)
        try:
            x_rel = x - self.centerx
            y_rel = y - self.centery
            x_new = self.centerx + x_rel * self._tilt_scale_x + self._tilt_shift_x
            y_new = self.centery + y_rel
            return (x_new, y_new)
        except Exception:
            return (x, y)

    def _apply_tilt_to_coords(self, coords):
        if not self._is_tilt_active():
            return tuple(coords)
        transformed = []
        coords_seq = list(coords)
        for i in range(0, len(coords_seq), 2):
            tx, ty = self._apply_tilt_to_point(coords_seq[i], coords_seq[i+1])
            transformed.extend((tx, ty))
        return tuple(transformed)

    def _apply_tilt_to_bbox(self, bbox):
        if not self._is_tilt_active():
            return bbox
        x0, y0, x1, y1 = bbox
        mid_y = (y0 + y1) / 2.0
        tx0, _ = self._apply_tilt_to_point(x0, mid_y)
        tx1, _ = self._apply_tilt_to_point(x1, mid_y)
        x_left = min(tx0, tx1)
        x_right = max(tx0, tx1)
        return (x_left, y0, x_right, y1)

    def _update_horizontal_tilt_button_label(self):
        if hasattr(self, 'horizontal_tilt_button'):
            try:
                self.horizontal_tilt_button.config(text=f"↔ 横向倾角 {self.horizontal_tilt_angle:+.1f}°")
            except Exception:
                pass

    def set_horizontal_tilt(self, value):
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return

        clamped = max(-5.0, min(5.0, numeric))
        if abs(clamped - self.horizontal_tilt_angle) < 1e-4:
            if self._tilt_var is not None:
                try:
                    if abs(self._tilt_var.get() - clamped) > 1e-4:
                        self._tilt_var.set(clamped)
                except Exception:
                    pass
            self._update_horizontal_tilt_button_label()
            return

        self.horizontal_tilt_angle = clamped
        self._update_tilt_params()
        if self._tilt_var is not None:
            try:
                if abs(self._tilt_var.get() - clamped) > 1e-4:
                    self._tilt_var.set(clamped)
            except Exception:
                pass

        self._update_horizontal_tilt_button_label()

        try:
            self.drawbackground()
            self.ensure_pointers_created()
            if hasattr(self, 'hand1'):
                self.mycanvas.coords(self.hand1, *self.coordinate_tip_line_A1())
            if hasattr(self, 'hand2'):
                self.mycanvas.coords(self.hand2, *self.coordinate_tip_line_A2())
            if hasattr(self, 'hand1_tip'):
                self.mycanvas.coords(self.hand1_tip, *self.coordinate_tip_line_A1())
            if hasattr(self, 'hand2_tip'):
                self.mycanvas.coords(self.hand2_tip, *self.coordinate_tip_line_A2())
        except Exception:
            pass

    def _on_tilt_window_closed(self):
        if self._tilt_window is not None:
            try:
                self._tilt_window.destroy()
            except Exception:
                pass
        self._tilt_window = None
        self._tilt_var = None

    def open_horizontal_tilt_dialog(self):
        if self._tilt_window is not None:
            try:
                if self._tilt_window.winfo_exists():
                    self._tilt_window.focus()
                    return
            except Exception:
                self._tilt_window = None

        tilt_window = tk.Toplevel(self)
        tilt_window.title("横向倾角调节")
        tilt_window.resizable(False, False)
        self._tilt_window = tilt_window

        tk.Label(tilt_window, text="模拟安装横向倾角 (±5°)", font=("Arial", 11, "bold")).pack(padx=20, pady=(15, 5))

        self._tilt_var = tk.DoubleVar(value=self.horizontal_tilt_angle)
        tilt_scale = tk.Scale(
            tilt_window,
            from_=-5.0,
            to=5.0,
            orient=tk.HORIZONTAL,
            resolution=0.1,
            length=240,
            variable=self._tilt_var,
            command=lambda v: self.set_horizontal_tilt(v)
        )
        tilt_scale.pack(padx=20, pady=5)

        tips = (
            "正值: 右侧偏远, 表盘向左倾斜",
            "负值: 左侧偏远, 表盘向右倾斜"
        )
        tk.Label(tilt_window, text="\n".join(tips), font=("Arial", 9), fg="#555555").pack(padx=20, pady=(0, 5))

        btn_frame = tk.Frame(tilt_window)
        btn_frame.pack(pady=(10, 15))

        def _reset_tilt():
            self.set_horizontal_tilt(0.0)

        tk.Button(btn_frame, text="复位", command=_reset_tilt).pack(side=tk.LEFT, padx=8)
        tk.Button(btn_frame, text="关闭", command=self._on_tilt_window_closed).pack(side=tk.LEFT, padx=8)

        tilt_window.protocol("WM_DELETE_WINDOW", self._on_tilt_window_closed)
        tilt_window.transient(self.winfo_toplevel())
        tilt_window.grab_set()

    def clear_mirrored_images(self):
        """清理镜像图像缓存"""
        if hasattr(self, '_mirrored_images'):
            self._mirrored_images.clear()

    def drawtickofA1(self): #draw tick mark of dial A1
        for i in range(self.numberofintervaloftickl):
            # 计算基础角度
            if self.is_mirrored:
                # 镜像状态：角度需要反向计算以实现正确的镜像效果
                angle = -i*self.intervaloftickl*2*mt.pi-self.phasedelaytozero
            else:
                # 正常状态
                angle = i*self.intervaloftickl*2*mt.pi-self.phasedelaytozero

            x1 = self.centerx+self.neftickmarkl*mt.cos(angle)
            y1 = self.centery+self.neftickmarkl*mt.sin(angle)
            x2 = self.centerx+self.feftickmarkl*mt.cos(angle)
            y2 = self.centery+self.feftickmarkl*mt.sin(angle)

            vectoroflongtick=self._apply_tilt_to_coords((x1, y1, x2, y2))
            self.mycanvas.create_line(vectoroflongtick,width=self.widthoftickA1,smooth=True,tags=('dial_static',))

            # 中间刻度线
            middle_angle = angle + self.phasedelayoftickmarkm
            x1_m = self.centerx+self.neftickmarkm*mt.cos(middle_angle)
            y1_m = self.centery+self.neftickmarkm*mt.sin(middle_angle)
            x2_m = self.centerx+self.feftickmarkm*mt.cos(middle_angle)
            y2_m = self.centery+self.feftickmarkm*mt.sin(middle_angle)

            # 镜像变换
            if self.is_mirrored:
                x1_m = 2*self.centerx - x1_m
                x2_m = 2*self.centerx - x2_m

            vectorofmiddletick=self._apply_tilt_to_coords((x1_m, y1_m, x2_m, y2_m))
            self.mycanvas.create_line(vectorofmiddletick,width=self.widthoftickA1,smooth=True,tags=('dial_static',))

        for i in range(self.numberofintervalofticks):
            # 小刻度线
            angle = i*self.intervalofticks*2*mt.pi-self.phasedelaytozero

            x1 = self.centerx+self.neftickmarks*mt.cos(angle)
            y1 = self.centery+self.neftickmarks*mt.sin(angle)
            x2 = self.centerx+self.feftickmarks*mt.cos(angle)
            y2 = self.centery+self.feftickmarks*mt.sin(angle)

            # 镜像变换
            if self.is_mirrored:
                x1 = 2*self.centerx - x1
                x2 = 2*self.centerx - x2

            x1_s, y1_s, x2_s, y2_s = self._apply_tilt_to_coords((x1, y1, x2, y2))
            self.mycanvas.create_line(x1_s, y1_s, x2_s, y2_s,
                                      width=self.widthoftickA1,smooth=True,tags=('dial_static',))

    def drawnumberofA1(self):
        for i in range(self.numberofintervaloftickl):
            # 计算基础角度
            if self.is_mirrored:
                # 镜像状态：角度需要反向计算以实现正确的镜像效果
                angle = -i*self.intervaloftickl*2*mt.pi-self.phasedelaytozero
            else:
                # 正常状态
                angle = i*self.intervaloftickl*2*mt.pi-self.phasedelaytozero

            x = self.centerx+self.lengthofnumber*mt.cos(angle)
            y = self.centery+self.lengthofnumber*mt.sin(angle)

            # 使用镜像文字方法（按缩放调整字号）
            try:
                font_size_a1 = max(8, int(38 * getattr(self, 'ui_scale', 1.0)))
            except Exception:
                font_size_a1 = 38
            self.create_mirrored_text(x, y, str(self.strofA1[i]),
                                    ("Times New Roman", font_size_a1))


    def drawtickofA2(self):
        for i in range(self.numberofintervaloftickofA2):
            # 计算基础角度
            if self.is_mirrored:
                # 镜像状态：角度需要反向计算，副表盘位置镜像
                angle = -i*self.intervaloftickofA2*2*mt.pi-self.phasedelaytozero
                center_a2_x = 2*self.centerx - self.centerofarmA2x
            else:
                # 正常状态
                angle = i*self.intervaloftickofA2*2*mt.pi-self.phasedelaytozero
                center_a2_x = self.centerofarmA2x

            x1 = center_a2_x+self.neftickmarkA2*mt.cos(angle)
            y1 = self.centerofarmA2y+self.neftickmarkA2*mt.sin(angle)
            x2 = center_a2_x+self.feftickmarkA2*mt.cos(angle)
            y2 = self.centerofarmA2y+self.feftickmarkA2*mt.sin(angle)

            vectoroftickofA2=self._apply_tilt_to_coords((x1, y1, x2, y2))
            self.mycanvas.create_line(vectoroftickofA2,width=self.widthoftickA2,smooth=True, tags=('dial_static',) )

    def drawnumberofA2(self):
        for i in range(self.numberofintervaloftickofA2):
            # 计算基础角度
            if self.is_mirrored:
                # 镜像状态：角度需要反向计算，副表盘位置镜像
                angle = i*self.intervaloftickofA2*2*mt.pi-self.phasedelaytozero
                center_a2_x = 2*self.centerx - self.centerofarmA2x
            else:
                # 正常状态
                angle = -i*self.intervaloftickofA2*2*mt.pi-self.phasedelaytozero
                center_a2_x = self.centerofarmA2x

            x = center_a2_x+self.lengthofnumberA2*mt.cos(angle)
            y = self.centerofarmA2y+self.lengthofnumberA2*mt.sin(angle)

            # 使用镜像文字方法（按缩放调整字号）
            try:
                font_size_a2 = max(8, int(16 * getattr(self, 'ui_scale', 1.0)))
            except Exception:
                font_size_a2 = 16
            self.create_mirrored_text(x, y, str(self.strofA2[i]),
                                    ("Times New Roman", font_size_a2, "bold"))

    def drawcircleedofA1(self):#draw the circle end of hand of A1
        # 根据中心偏移移动指针中心圆
        cx = self.centerx + (self.center_offset_dx if self.center_offset_enabled else 0)
        cy = self.centery + (self.center_offset_dy if self.center_offset_enabled else 0)
        circleedofA1=(cx-self.radiusofcircleofhand1,
                      cy-self.radiusofcircleofhand1,
                      cx+self.radiusofcircleofhand1,
                      cy+self.radiusofcircleofhand1)
        outer_bbox = self._apply_tilt_to_bbox(circleedofA1)
        self.mycanvas.create_oval(outer_bbox, outline="black", fill="black", width=1, tags=('dial_static',))

        ix, iy = self._apply_tilt_to_point(cx, cy)
        inner_oval = (ix-1, iy-1, ix+1, iy+1)
        self.mycanvas.create_oval(inner_oval, outline="white", fill="white", width=0, tags=('dial_static',))

    def drawcircleedofA2(self):#draw the circle end of hand of A2
        center_x = self.centerofarmA2x
        center_y = self.centerofarmA2y

        # 如果镜像，调整A2指针中心的x坐标
        if self.is_mirrored:
            center_x = 2*self.centerx - self.centerofarmA2x

        circleeofA2=(center_x-self.radiusofcircleofhand2,
                     center_y-self.radiusofcircleofhand2,
                     center_x+self.radiusofcircleofhand2,
                     center_y+self.radiusofcircleofhand2)
        outer_bbox = self._apply_tilt_to_bbox(circleeofA2)
        self.mycanvas.create_oval(outer_bbox, outline="black", fill="black", width=1, tags=('dial_static',))

        ix2, iy2 = self._apply_tilt_to_point(center_x, center_y)
        inner_oval2 = (ix2-1, iy2-1, ix2+1, iy2+1)
        self.mycanvas.create_oval(inner_oval2, outline="white", fill="white", width=0, tags=('dial_static',))

    def drawcirclebofA2(self):#draw the circle boundary of dial A2
        center_x = self.centerofarmA2x
        center_y = self.centerofarmA2y

        # 如果镜像，调整A2表盘中心的x坐标
        if self.is_mirrored:
            center_x = 2*self.centerx - self.centerofarmA2x

        circlebofA2=(center_x-self.radiusfdialA2,
                     center_y-self.radiusfdialA2,
                     center_x+self.radiusfdialA2,
                     center_y+self.radiusfdialA2)
        bbox = self._apply_tilt_to_bbox(circlebofA2)
        self.mycanvas.create_oval(bbox, outline="black", fill="white", width=self.widthofdialA2, tags=('dial_static',))


    def drawbackground(self): #draw backgound of dial gauge
        # 清理之前的镜像图像缓存
        self.clear_mirrored_images()

        # 删除旧的表盘静态元素
        try:
            self.mycanvas.delete('dial_static')
        except Exception:
            pass

        # 填充主表盘白色圆面（防止黑色背景透出）
        dial_bbox=(self.centerx-self.radiusofdialA1,
                   self.centery-self.radiusofdialA1,
                   self.centerx+self.radiusofdialA1,
                   self.centery+self.radiusofdialA1)
        dial_bbox_t = self._apply_tilt_to_bbox(dial_bbox)
        try:
            self.mycanvas.create_oval(dial_bbox_t, outline="white", fill="white", width=0, tags=('dial_static',))
        except Exception:
            pass

        # 先绘制主表盘刻度（倾斜开启时改用逐线绘制）
        use_agg = PIL_AVAILABLE and AGGDRAW_AVAILABLE and not self._is_tilt_active()
        if use_agg:
            try:
                self._draw_a1_ticks_agg()
            except Exception:
                self.drawtickofA1()
        else:
            if hasattr(self, '_a1_ticks_item') and getattr(self, '_a1_ticks_item', None):
                try:
                    self.mycanvas.delete(self._a1_ticks_item)
                except Exception:
                    pass
                self._a1_ticks_item = None
            self.drawtickofA1()

        # 其余静态内容
        self.drawnumberofA1()
        self.drawcircleedofA1()
        # 先铺白并绘制A2外圈，再绘制A2刻度与数字，避免被覆盖
        self.drawcirclebofA2()
        self.drawtickofA2()
        self.drawnumberofA2()
        self.drawcircleedofA2()

        # 最后确保指针图元已创建，并根据当前可见性设置显示状态
        self.ensure_pointers_created()
        try:
            state = 'normal' if getattr(self, 'pointers_visible', True) else 'hidden'
            for it in (self.hand1, self.hand2, getattr(self, 'hand1_tip', None), getattr(self, 'hand2_tip', None)):
                if it is not None:
                    self.mycanvas.itemconfigure(it, state=state)
            if hasattr(self, 'hand1'):
                self.mycanvas.coords(self.hand1, *self.coordinate_tip_line_A1())
            if hasattr(self, 'hand2'):
                self.mycanvas.coords(self.hand2, *self.coordinate_tip_line_A2())
            if hasattr(self, 'hand1_tip'):
                self.mycanvas.coords(self.hand1_tip, *self.coordinate_tip_line_A1())
            if hasattr(self, 'hand2_tip'):
                self.mycanvas.coords(self.hand2_tip, *self.coordinate_tip_line_A2())
            try:
                self.mycanvas.tag_raise('needle')
                for it in (getattr(self, 'hand1_tip', None), getattr(self, 'hand2_tip', None)):
                    if it is not None:
                        self.mycanvas.tag_raise(it)
            except Exception:
                pass
        except Exception:
            pass

        # 若启用中心偏移，标注两个中心点
        if getattr(self, 'center_offset_enabled', False):
            r = max(2, int(6*self.ui_scale))
            # 表盘中心（蓝）
            center_main_bbox = self._apply_tilt_to_bbox((self.centerx-r, self.centery-r, self.centerx+r, self.centery+r))
            self.mycanvas.create_oval(center_main_bbox, fill="#1E90FF", width=0, tags=('dial_static',))
            # 指针中心（红）
            cx = self.centerx + self.center_offset_dx
            cy = self.centery + self.center_offset_dy
            center_offset_bbox = self._apply_tilt_to_bbox((cx-r, cy-r, cx+r, cy+r))
            self.mycanvas.create_oval(center_offset_bbox, fill="#FF4500", width=0, tags=('dial_static',))



    def _canvas_item_exists(self, item_id):
        try:
            return bool(self.mycanvas.type(item_id))
        except Exception:
            return False

    def ensure_pointers_created(self):
        """一次性创建指针图元；后续仅更新坐标/状态，避免反复创建导致闪烁。
        指针主体改为粗线条（圆端），与刻线一致风格，抗锯齿效果更好。
        """
        # hand1 主体（粗线，直端帽，避免端点外扩）
        if not hasattr(self, 'hand1') or not self._canvas_item_exists(self.hand1):
            try:
                body_w_a1 = int(getattr(self, 'widthoftickA1', 2))
                self.hand1 = self.mycanvas.create_line(
                    *self.coordinate_tip_line_A1(),
                    fill=self.pointer_color,
                    width=body_w_a1,
                    capstyle=tk.BUTT,
                    tags=('needle',)
                )
            except Exception:
                pass
        # hand2 主体（粗线，直端帽，避免端点外扩）
        if not hasattr(self, 'hand2') or not self._canvas_item_exists(self.hand2):
            try:
                body_w_a2 = int(getattr(self, 'widthoftickA2', 2))
                self.hand2 = self.mycanvas.create_line(
                    *self.coordinate_tip_line_A2(),
                    fill=self.pointer_color,
                    width=body_w_a2,
                    capstyle=tk.BUTT,
                    tags=('needle',)
                )
            except Exception:
                pass

    # --------- 指针平滑与对齐辅助函数 ---------
    def _snap_angle(self, angle: float, step: float, epsilon: float) -> float:
        try:
            if step <= 0:
                return angle
            k = round(angle / step)
            snapped = k * step
            if abs(angle - snapped) <= epsilon:
                return snapped
        except Exception:
            pass
        return angle

    def _quantize_line_coords(self, x0: float, y0: float, x1: float, y1: float, width: int):
        # 将端点量化到0.5像素网格，减少走样；偶数宽度优先整数网格
        try:
            if int(width) % 2 == 0:
                q = 1.0
            else:
                q = 0.5
            def _q(v):
                return round(v / q) * q
            return (_q(x0), _q(y0), _q(x1), _q(y1))
        except Exception:
            return (x0, y0, x1, y1)

    def coordinateofA1(self): #compute the coordinates of hand A1 for trangle shape hand
        integer_part=int(self.lengthofmeas)
        fractional_part=round(self.lengthofmeas-integer_part,6)  # 提高精度到6位小数
        # 应用中心偏移
        x0 = self.centerx + (self.center_offset_dx if self.center_offset_enabled else 0)
        y0 = self.centery + (self.center_offset_dy if self.center_offset_enabled else 0)
        adjustangle=(1/4)*mt.pi #for create the hand1's shape as triangle
        angle=fractional_part*(2*mt.pi)

        # 缓存常用计算 - 更细的指针
        radiust=max(1, int(5 * getattr(self, 'ui_scale', 1.0)))  # scaled
        # 针尖长度与长刻度外端一致，确保重合
        radiush=float(self.feftickmarkl)

        if self.is_mirrored:
            # 镜像状态：保持指针完整性，统一使用镜像角度
            base_angle = angle + self.phasedelaytozero
            # 确保所有三个顶点使用相同的角度基准
            cos_base = mt.cos(base_angle)
            sin_base = mt.sin(base_angle)
            cos_adj1 = mt.cos(base_angle - adjustangle)
            sin_adj1 = mt.sin(base_angle - adjustangle)
            cos_adj2 = mt.cos(base_angle + adjustangle)
            sin_adj2 = mt.sin(base_angle + adjustangle)
        else:
            # 正常状态：保持原有逻辑
            base_angle = -angle + self.phasedelaytozero
            cos_base = mt.cos(base_angle)
            sin_base = mt.sin(base_angle)
            cos_adj1 = mt.cos(base_angle - adjustangle)
            sin_adj1 = mt.sin(base_angle - adjustangle)
            cos_adj2 = mt.cos(base_angle + adjustangle)
            sin_adj2 = mt.sin(base_angle + adjustangle)

        # 计算指针的三个顶点坐标
        x1=x0+radiust*cos_adj1
        y1=y0-radiust*sin_adj1
        x2=x0+radiust*cos_adj2
        y2=y0-radiust*sin_adj2
        x3=x0+radiush*cos_base
        y3=y0-radiush*sin_base

        return self._apply_tilt_to_coords((x1,y1,x2,y2,x3,y3))

    def coordinateA1ini(self): #coordinates of hand A1 for trangle shape hand init
        # 应用中心偏移
        x0 = self.centerx + (self.center_offset_dx if self.center_offset_enabled else 0)
        y0 = self.centery + (self.center_offset_dy if self.center_offset_enabled else 0)
        adjustangle=(1/4)*mt.pi #for create the hand1's shape as triangle
        angle=0
        radiust=max(1, int(10 * getattr(self, 'ui_scale', 1.0)))  # scaled
        # 初始针尖长度与长刻度外端一致
        radiush=float(self.feftickmarkl)

        # 根据镜像状态计算基础角度，与coordinateofA1()保持一致
        if self.is_mirrored:
            # 镜像状态：保持指针完整性，统一使用镜像角度
            base_angle = angle + self.phasedelaytozero
            cos_base = mt.cos(base_angle)
            sin_base = mt.sin(base_angle)
            cos_adj1 = mt.cos(base_angle - adjustangle)
            sin_adj1 = mt.sin(base_angle - adjustangle)
            cos_adj2 = mt.cos(base_angle + adjustangle)
            sin_adj2 = mt.sin(base_angle + adjustangle)
        else:
            # 正常状态：保持原有逻辑
            base_angle = -angle + self.phasedelaytozero
            cos_base = mt.cos(base_angle)
            sin_base = mt.sin(base_angle)
            cos_adj1 = mt.cos(base_angle - adjustangle)
            sin_adj1 = mt.sin(base_angle - adjustangle)
            cos_adj2 = mt.cos(base_angle + adjustangle)
            sin_adj2 = mt.sin(base_angle + adjustangle)

        # 计算指针的三个顶点坐标
        x1=x0+radiust*cos_adj1
        y1=y0-radiust*sin_adj1
        x2=x0+radiust*cos_adj2
        y2=y0-radiust*sin_adj2
        x3=x0+radiush*cos_base
        y3=y0-radiush*sin_base

        return self._apply_tilt_to_coords((x1,y1,x2,y2,x3,y3))

    # 使用 aggdraw 抗锯齿绘制A1刻度到离屏图像，再缩放贴到Canvas
    def _draw_a1_ticks_agg(self):
        scale_os = 2  # 超采样倍数
        size = int(self.canvaslength*scale_os)
        img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
        draw = aggdraw.Draw(img)

        # 画长刻度/中刻度/小刻度
        def _line(pen, x1, y1, x2, y2):
            draw.line((x1*scale_os, y1*scale_os, x2*scale_os, y2*scale_os), pen)

        # 笔宽与颜色
        pen_long = aggdraw.Pen('black', max(1, int(self.widthoftickA1*scale_os)))
        pen_mid = aggdraw.Pen('black', max(1, int(self.widthoftickA1*scale_os)))
        pen_short = aggdraw.Pen('black', max(1, int(self.widthoftickA1*scale_os)))

        # 长刻度和中刻度
        for i in range(self.numberofintervaloftickl):
            # 与 drawtickofA1 一致的角度处理
            if self.is_mirrored:
                angle = -i*self.intervaloftickl*2*mt.pi-self.phasedelaytozero
            else:
                angle = i*self.intervaloftickl*2*mt.pi-self.phasedelaytozero

            x1 = self.centerx+self.neftickmarkl*mt.cos(angle)
            y1 = self.centery+self.neftickmarkl*mt.sin(angle)
            x2 = self.centerx+self.feftickmarkl*mt.cos(angle)
            y2 = self.centery+self.feftickmarkl*mt.sin(angle)
            _line(pen_long, x1, y1, x2, y2)

            middle_angle = angle + self.phasedelayoftickmarkm
            x1_m = self.centerx+self.neftickmarkm*mt.cos(middle_angle)
            y1_m = self.centery+self.neftickmarkm*mt.sin(middle_angle)
            x2_m = self.centerx+self.feftickmarkm*mt.cos(middle_angle)
            y2_m = self.centery+self.feftickmarkm*mt.sin(middle_angle)
            if self.is_mirrored:
                x1_m = 2*self.centerx - x1_m
                x2_m = 2*self.centerx - x2_m
            _line(pen_mid, x1_m, y1_m, x2_m, y2_m)

        # 小刻度
        for i in range(self.numberofintervalofticks):
            angle = i*self.intervalofticks*2*mt.pi-self.phasedelaytozero
            x1 = self.centerx+self.neftickmarks*mt.cos(angle)
            y1 = self.centery+self.neftickmarks*mt.sin(angle)
            x2 = self.centerx+self.feftickmarks*mt.cos(angle)
            y2 = self.centery+self.feftickmarks*mt.sin(angle)
            if self.is_mirrored:
                x1 = 2*self.centerx - x1
                x2 = 2*self.centerx - x2
            _line(pen_short, x1, y1, x2, y2)

        draw.flush()
        img_small = img.resize((self.canvaslength, self.canvaslength), Image.LANCZOS)
        self._a1_ticks_photo = ImageTk.PhotoImage(img_small)
        # 清理旧图像
        if hasattr(self, '_a1_ticks_item') and self._a1_ticks_item:
            try:
                self.mycanvas.delete(self._a1_ticks_item)
            except Exception:
                pass
        self._a1_ticks_item = self.mycanvas.create_image(self.centerx, self.centery, image=self._a1_ticks_photo, tags=('dial_static',))

    def coordinateofA2(self):
        if self.lengthofmeas>self.rangeupperbound:
            print("the lenght overflow")# that could be a problem
        else:
            # 确定A2表盘中心位置
            if self.is_mirrored:
                x0 = 2*self.centerx - self.centerofarmA2x
                # 镜像状态：保持指针完整性，统一角度计算
                angle=(0.1*self.lengthofmeas)*(2*mt.pi)
                base_angle = -angle + self.phasedelaytozero
            else:
                x0 = self.centerofarmA2x
                # 正常状态
                angle=-(0.1*self.lengthofmeas)*(2*mt.pi)
                base_angle = -angle + self.phasedelaytozero

            y0 = self.centerofarmA2y
            adjustangle=(1/20)*mt.pi

            radiust=max(1, int(19 * getattr(self, 'ui_scale', 1.0)))
            # 副表针尖长度与A2刻度外端一致
            radiush=float(self.feftickmarkA2)

            # 统一使用base_angle确保指针完整性
            x1=x0-radiust*mt.cos(base_angle-adjustangle)
            y1=y0+radiust*mt.sin(base_angle-adjustangle)
            x2=x0-radiust*mt.cos(base_angle+adjustangle)
            y2=y0+radiust*mt.sin(base_angle+adjustangle)
            x3=x0+radiush*mt.cos(base_angle)
            y3=y0-radiush*mt.sin(base_angle)

            return self._apply_tilt_to_coords((x1,y1,x2,y2,x3,y3))

    def coordinateA2ini(self):
        # 确定A2表盘中心位置，与coordinateofA2()保持一致
        if self.is_mirrored:
            x0 = 2*self.centerx - self.centerofarmA2x
            # 镜像状态：保持指针完整性，统一角度计算
            angle=(0.1*0)*(2*mt.pi)  # 初始角度为0
            base_angle = -angle + self.phasedelaytozero
        else:
            x0 = self.centerofarmA2x
            # 正常状态
            angle=-(0.1*0)*(2*mt.pi)  # 初始角度为0
            base_angle = -angle + self.phasedelaytozero

        y0 = self.centerofarmA2y
        adjustangle=(1/20)*mt.pi
        radiust=max(1, int(19 * getattr(self, 'ui_scale', 1.0)))
        # 初始长度与A2刻度外端一致
        radiush=float(self.feftickmarkA2)

        x1=x0-radiust*mt.cos(base_angle-adjustangle)
        y1=y0+radiust*mt.sin(base_angle-adjustangle)
        x2=x0-radiust*mt.cos(base_angle+adjustangle)
        y2=y0+radiust*mt.sin(base_angle+adjustangle)
        x3=x0+radiush*mt.cos(base_angle)
        y3=y0-radiush*mt.sin(base_angle)

        return self._apply_tilt_to_coords((x1,y1,x2,y2,x3,y3))

    # 叠加针尖细线：返回中心->针尖两点坐标，宽度与刻线一致
    def coordinate_tip_line_A1(self):
        integer_part=int(self.lengthofmeas)
        fractional_part=round(self.lengthofmeas-integer_part,6)
        x0 = self.centerx + (self.center_offset_dx if self.center_offset_enabled else 0)
        y0 = self.centery + (self.center_offset_dy if self.center_offset_enabled else 0)
        # 原始角度
        base_angle = (fractional_part*(2*mt.pi)+self.phasedelaytozero) if self.is_mirrored else (-fractional_part*(2*mt.pi)+self.phasedelaytozero)
        # 贴合刻线：小刻度步进
        try:
            step = (2*mt.pi) * float(getattr(self, 'intervalofticks', 0.01))
            eps = step * 0.18
            # 相对零点的角度做吸附
            rel = base_angle - self.phasedelaytozero
            rel = self._snap_angle(rel, step, eps)
            base_angle = rel + self.phasedelaytozero
        except Exception:
            pass
        x_tip = x0 + self.feftickmarkl*mt.cos(base_angle)
        y_tip = y0 - self.feftickmarkl*mt.sin(base_angle)
        quantized = self._quantize_line_coords(x0, y0, x_tip, y_tip, int(getattr(self, 'widthoftickA1', 2)))
        return self._apply_tilt_to_coords(quantized)

    def coordinate_tip_line_A2(self):
        if self.is_mirrored:
            x0 = 2*self.centerx - self.centerofarmA2x
            angle=(0.1*self.lengthofmeas)*(2*mt.pi)
            base_angle = -angle + self.phasedelaytozero
        else:
            x0 = self.centerofarmA2x
            angle=-(0.1*self.lengthofmeas)*(2*mt.pi)
            base_angle = -angle + self.phasedelaytozero
        y0 = self.centerofarmA2y
        # A2刻线吸附（与A2刻度分度一致）
        try:
            step = (2*mt.pi) * float(getattr(self, 'intervaloftickofA2', 0.1))
            eps = step * 0.22
            rel = base_angle - self.phasedelaytozero
            rel = self._snap_angle(rel, step, eps)
            base_angle = rel + self.phasedelaytozero
        except Exception:
            pass
        x_tip = x0 + self.feftickmarkA2*mt.cos(base_angle)
        y_tip = y0 - self.feftickmarkA2*mt.sin(base_angle)
        quantized = self._quantize_line_coords(x0, y0, x_tip, y_tip, int(getattr(self, 'widthoftickA2', 2)))
        return self._apply_tilt_to_coords(quantized)





    def updateback(self):  #dialgauge runing backwards
        if self.running:
            self.timeinterval=self.pauseduration[0]
            randnum=1 #step length of increase
            if self.lengthofmeas<=self.rangeupperbound:
                self.lengthofmeas=self.lengthofmeas-self.increaseinterval #the minus sign means the lenghtof meas decrease

            self.pausenumber=self.pausenumber+randnum
            self.lengthofmeas=round(self.lengthofmeas,4)
            self.indicator.configure(text="{:.4f}".format(self.lengthofmeas)) #update the indicator
            self.mycanvas.coords(self.hand1,self.coordinateofA1()) #update the coordinate of the hand1
            self.mycanvas.coords(self.hand2,self.coordinateofA2()) #update the coordinate of the hand2

            #判断是否需要暂停
            if(self.lengthofmeas<self.numberofpiecewise):
                if self.pausenumber*self.increaseinterval==self.lengthtopause[0]:
                    self.pausenumber=0
                    self.timeinterval=self.pauseduration[1]

            #判断是否需要暂停
            if(self.lengthofmeas>=self.numberofpiecewise):
                if self.pausenumber*self.increaseinterval==self.lengthtopause[1]:
                    self.pausenumber=0
                    self.timeinterval=self.pauseduration[1]
            #判断是否需要继续运行
            if self.lengthofmeas<=self.rangeupperbound:
                self.mycanvas.after(self.timeinterval,self.updateback)
        else:
            self.mycanvas.after(self.gaugewaitingduration,self.updateback)

    def update(self):
        if self.running:
            # 连续移动模式 - 按预设点顺序移动
                if not self.moving_to_preset and not self.preset_cycle_complete:
                    # 获取下一个目标预设点
                    if self.target_preset_index < len(self.preset_positions):
                        target_preset = self.preset_positions[self.target_preset_index]

                        # 简化的方向逻辑：根据数值大小关系确定转动方向
                        current_pos = self.lengthofmeas

                        # 直接根据数值大小关系确定方向
                        if current_pos < target_preset:
                            # 预设点数值更大：正向转动（顺时针）
                            self.lengthofmeas += self.increaseinterval
                            move_direction = "forward"
                        elif current_pos > target_preset:
                            # 预设点数值更小：反向转动（逆时针）
                            self.lengthofmeas -= self.increaseinterval
                            move_direction = "backward"
                        else:
                            move_direction = "arrived"

                        # 处理边界情况
                        if self.lengthofmeas > self.rangeupperbound:
                            self.lengthofmeas = self.rangeupperbound
                        elif self.lengthofmeas < 0:
                            self.lengthofmeas = 0

                        # 检查是否到达目标预设点
                        if abs(self.lengthofmeas - target_preset) <= self.increaseinterval * 2 or move_direction == "arrived":
                            self.lengthofmeas = target_preset  # 精确对齐
                            self.moving_to_preset = True
                            self.target_preset = target_preset

                            # 强制显示指针并更新按钮状态
                            self.force_show_pointers_at_preset()

                            # 记录到达预设点的历史数据
                            self.record_preset_reached(target_preset)
                            # 更新状态显示
                            self.update_position_info()
                            # 根据触发模式开始暂停/等待
                            if getattr(self, 'trigger_mode', 'time') == 'time':
                                # 进入暂停前刷新一次坐标，避免残影
                                if hasattr(self, 'hand1') and hasattr(self, 'hand2'):
                                    self.mycanvas.coords(self.hand1, self.coordinateofA1())
                                    self.mycanvas.coords(self.hand2, self.coordinateofA2())
                                self.mycanvas.after(self.pause_duration, self.resume_movement)
                            else:
                                # 位移触发：两阶段检测机制
                                # 第一阶段：等待静止（连续N次变化小于静止阈值）
                                self._ensure_sensor_vars()
                                self._sensor_state = 'await_still'
                                self._sensor_prev_value = None
                                self._sensor_still_count = 0
                                self._sensor_baseline = None
                                try:
                                    self._det_status_var.set(f"等待静止(0/{self.still_confirm_count})")
                                except Exception:
                                    pass
                                # 启动监控
                                self._sensor_start()
                                # 如果没有串口或启动失败，则显示"Continue"按钮以手动继续
                                if not getattr(self, '_sensor_started', False):
                                    try:
                                        py0 = int(self.canvaslength + 20*self.ui_scale)
                                        cx = int(self.centerx)
                                        step = int(120*self.ui_scale)
                                        self.mycanvas.coords(self.disp_continue_window, cx + step, py0 + int(130*self.ui_scale))
                                    except Exception:
                                        pass
                            print(f"到达预设点: {target_preset:.4f} (路径: {move_direction})")
                    else:
                        # 所有预设点都已访问完成
                        self.preset_cycle_complete = True
                        self.running = False
                        self.stop_after_cycle_complete()  # 循环完成后的特殊停止
                        return

                # 更新显示
                self.update_display()

                # 继续动画循环 - 使用用户控制的速度间隔
                self.mycanvas.after(int(self.pauseduration[0]), self.update)
        else:
            self.mycanvas.after(self.gaugewaitingduration, self.update)

    def resume_movement(self):
        """恢复移动（暂停结束后调用）"""
        self.moving_to_preset = False
        self.target_preset = None

        # 恢复预设点暂停前的指针状态
        self.pointers_visible = self.pointers_visible_before_preset

        if self.pointers_visible:
            # 恢复显示状态
            self.pointer_toggle_button.config(text="👁 Hide Pointers", bg="#FFB6C1", activebackground="#FF91A4")
            # 仅确保存在并设为可见
            self.ensure_pointers_created()
            try:
                for it in (self.hand1, self.hand2, getattr(self, 'hand1_tip', None), getattr(self, 'hand2_tip', None)):
                    if it is not None:
                        self.mycanvas.itemconfigure(it, state='normal')
            except Exception:
                pass
        else:
            # 恢复隐藏状态
            self.pointer_toggle_button.config(text="👁 Show Pointers", bg="#90EE90", activebackground="#7FDD7F")
            # 不删除，改为隐藏避免闪烁
            try:
                for it in (getattr(self, 'hand1', None), getattr(self, 'hand2', None), getattr(self, 'hand1_tip', None), getattr(self, 'hand2_tip', None)):
                    if it is not None:
                        self.mycanvas.itemconfigure(it, state='hidden')
            except Exception:
                pass
            print("恢复指针隐藏状态")

        # 重置两阶段检测状态（放在最后，避免影响指针重建）
        self._sensor_state = 'idle'
        self._sensor_prev_value = None
        self._sensor_still_count = 0
        self._sensor_baseline = None
        try:
            self._det_status_var.set("空闲")
        except Exception:
            pass

        # 移动到下一个预设点
        self.target_preset_index += 1
        self.update_position_info()

    # ---------------- 位移传感器集成 ----------------
    def _ensure_sensor_vars(self):
        if self._sensor_status_var is None:
            self._sensor_status_var = tk.StringVar(value="断开")
        if self._sensor_value_var is None:
            self._sensor_value_var = tk.StringVar(value="--.-- mm")
        if getattr(self, '_det_status_var', None) is None:
            self._det_status_var = tk.StringVar(value="空闲")

    def _sensor_update_status(self, text: str):
        self._ensure_sensor_vars()
        self._sensor_status_var.set(text)

    def _sensor_update_value(self, val: float):
        self._ensure_sensor_vars()
        try:
            self._sensor_value_var.set(f"{val:.4f} mm")
        except Exception:
            self._sensor_value_var.set("--.-- mm")

    def _sensor_start(self):
        if self._sensor_started:
            return
        if serial is None:
            try:
                tk.messagebox.showerror("错误", "未安装pyserial，无法启动位移传感器监控")
            except Exception:
                pass
            return
        with self._sensor_lock:
            if self._sensor_started:
                return
            try:
                self._sensor_ser = serial.Serial(_MV_PORT, _MV_BAUD, timeout=0.1)
                self._sensor_started = True
                self._sensor_update_status("连接")
                t1 = threading.Thread(target=self._sensor_reader, daemon=True)
                t2 = threading.Thread(target=self._sensor_sender, daemon=True)
                self._sensor_threads = [t1, t2]
                for t in self._sensor_threads:
                    t.start()
            except Exception as e:
                self._sensor_update_status("断开")
                try:
                    tk.messagebox.showerror("串口错误", f"无法打开传感器串口: {e}")
                except Exception:
                    pass

    def _sensor_stop(self):
        with self._sensor_lock:
            self._sensor_started = False
            try:
                if self._sensor_ser and getattr(self._sensor_ser, 'is_open', False):
                    self._sensor_ser.close()
            except Exception:
                pass
            self._sensor_ser = None
            self._sensor_update_status("断开")
            # 重置两阶段检测状态
            self._sensor_state = 'idle'
            self._sensor_prev_value = None
            self._sensor_still_count = 0
            self._sensor_baseline = None
            try:
                self._det_status_var.set("空闲")
            except Exception:
                pass

    def _sensor_reader(self):
        buffer = bytearray()
        while self._sensor_started:
            try:
                ser = self._sensor_ser
                if ser and ser.in_waiting:
                    buffer.extend(ser.read(ser.in_waiting))
                    while len(buffer) >= 9:
                        if buffer[0] != 0x01:
                            buffer.pop(0)
                            continue
                        frame = bytes(buffer[:9])
                        if _mv_verify(frame):
                            buffer = buffer[9:]
                            disp_mm, _ = _mv_parse(frame)
                            if disp_mm is not None:
                                # 显示当前值
                                self.after(0, lambda v=disp_mm: self._sensor_update_value(v))

                                # 仅在"位移触发 且 正在预设点等待"时进行两阶段检测
                                if getattr(self, 'trigger_mode', 'time') != 'displacement' or not self.moving_to_preset:
                                    self._sensor_state = 'idle'
                                    self._sensor_prev_value = None
                                    self._sensor_still_count = 0
                                    self._sensor_baseline = None
                                else:
                                    # 两阶段状态机：await_still -> await_change -> 触发
                                    if self._sensor_state == 'await_still':
                                        # 连续N次 |Δ| < still_threshold 视为静止
                                        if self._sensor_prev_value is not None:
                                            if abs(disp_mm - self._sensor_prev_value) < float(self.still_threshold):
                                                self._sensor_still_count += 1
                                            else:
                                                self._sensor_still_count = 0
                                        self._sensor_prev_value = disp_mm

                                        cnt = int(self.still_confirm_count)
                                        if self._sensor_still_count >= cnt:
                                            self._sensor_state = 'await_change'
                                            self._sensor_baseline = disp_mm
                                            self._sensor_still_count = 0
                                            try:
                                                self.after(0, lambda: self._det_status_var.set("已静止，等待变化"))
                                            except Exception:
                                                pass
                                        else:
                                            try:
                                                self.after(0, lambda c=self._sensor_still_count, n=self.still_confirm_count: self._det_status_var.set(f"等待静止({c}/{n})"))
                                            except Exception:
                                                pass

                                    elif self._sensor_state == 'await_change':
                                        if self._sensor_baseline is None:
                                            self._sensor_baseline = disp_mm
                                        if abs(disp_mm - float(self._sensor_baseline)) > float(self.sensor_threshold):
                                            # 检测到变化，触发移动
                                            try:
                                                self.after(0, lambda: self._det_status_var.set("检测到变化，执行移动"))
                                            except Exception:
                                                pass
                                            self._sensor_state = 'idle'
                                            if self.moving_to_preset and getattr(self, 'trigger_mode', 'time') == 'displacement':
                                                self.after(0, self.notify_displacement_change)
                                        else:
                                            # 仍在等待变化
                                            pass

                                    else:
                                        # idle 状态，等到达预设点时会进入 await_still
                                        pass
                        else:
                            buffer.pop(0)
                time.sleep(0.002)
            except Exception:
                time.sleep(0.1)

    def _sensor_sender(self):
        while self._sensor_started:
            try:
                ser = self._sensor_ser
                if ser:
                    ser.write(_MV_MSG)
                time.sleep(_MV_INTERVAL)
            except Exception:
                time.sleep(0.2)

        self.target_preset = None


    def update_display(self):
        """更新显示内容"""
        # 更新指示器（加入平滑插值，让后两位小数随移动而变化）
        try:
            target = float(self.lengthofmeas)
        except Exception:
            target = self.lengthofmeas
        # 线性插值，步进与速度相关；避免过冲
        delta = target - self._display_value
        self._display_value += delta * 0.5 if abs(delta) > 1e-6 else delta
        new_text = "{:.4f}".format(self._display_value)
        if new_text != self.last_indicator_text:
            self.indicator.configure(text=new_text)
            self.last_indicator_text = new_text

        # 更新指针位置（始终更新，显示由state控制）
        if hasattr(self, 'hand1') and hasattr(self, 'hand2'):
            # 始终更新坐标（即便隐藏也更新），避免显示时跳变
            try:
                self.mycanvas.coords(self.hand1, *self.coordinate_tip_line_A1())
                self.mycanvas.coords(self.hand2, *self.coordinate_tip_line_A2())
                if hasattr(self, 'hand1_tip'):
                    self.mycanvas.coords(self.hand1_tip, *self.coordinate_tip_line_A1())
                if hasattr(self, 'hand2_tip'):
                    self.mycanvas.coords(self.hand2_tip, *self.coordinate_tip_line_A2())
            except Exception:
                pass
            # 可见性按当前标志控制
            state = 'normal' if self.pointers_visible else 'hidden'
            try:
                for it in (self.hand1, self.hand2, getattr(self, 'hand1_tip', None), getattr(self, 'hand2_tip', None)):
                    if it is not None:
                        self.mycanvas.itemconfigure(it, state=state)
            except Exception:
                pass
            # 重新标注中心点（若启用）
            if getattr(self, 'center_offset_enabled', False):
                # 先清除上一次标注：简化处理，整幅背景会在drawbackground时刷新。
                pass

    # 线型坐标函数已移除（保持三角形指针）

    # 遮罩小方块：3x3，可拖动，位于刻线之上、指针之下
    def add_mask_box(self):
        size_w, size_h = 3, 10
        cx, cy = self.centerx, self.centery
        angle_deg = 0

        def _rect_points(cx, cy, w, h, ang_deg):
            ang = mt.radians(ang_deg)
            cw, ch = w/2.0, h/2.0
            corners = [(-cw,-ch),(cw,-ch),(cw,ch),(-cw,ch)]
            pts = []
            cos_a = mt.cos(ang); sin_a = mt.sin(ang)
            for (x,y) in corners:
                rx = x*cos_a - y*sin_a + cx
                ry = x*sin_a + y*cos_a + cy
                pts.extend([rx, ry])
            return pts

        item = self.mycanvas.create_polygon(_rect_points(cx, cy, size_w, size_h, angle_deg),
                                            fill='white', outline='white')
        self._mask_items.append(item)

        state = {'dx':0,'dy':0,'cx':cx,'cy':cy,'ang':angle_deg,'w':size_w,'h':size_h}

        def _start(e, it=item, st=state):
            st['dx'] = self.mycanvas.canvasx(e.x) - st['cx']
            st['dy'] = self.mycanvas.canvasy(e.y) - st['cy']

        def _drag(e, it=item, st=state):
            st['cx'] = self.mycanvas.canvasx(e.x) - st['dx']
            st['cy'] = self.mycanvas.canvasy(e.y) - st['dy']
            self.mycanvas.coords(it, *_rect_points(st['cx'], st['cy'], st['w'], st['h'], st['ang']))

        def _rot_start(e, it=item, st=state):
            # 右键按下开始旋转，记录相对角度
            px = self.mycanvas.canvasx(e.x)
            py = self.mycanvas.canvasy(e.y)
            st['ang0'] = st['ang']
            st['a_start'] = mt.degrees(mt.atan2(py - st['cy'], px - st['cx']))

        def _rot_drag(e, it=item, st=state):
            px = self.mycanvas.canvasx(e.x)
            py = self.mycanvas.canvasy(e.y)
            a_cur = mt.degrees(mt.atan2(py - st['cy'], px - st['cx']))
            st['ang'] = (st['ang0'] + (a_cur - st['a_start'])) % 360
            self.mycanvas.coords(it, *_rect_points(st['cx'], st['cy'], st['w'], st['h'], st['ang']))

        # 绑定拖动与旋转（滚轮）
        self.mycanvas.tag_bind(item, '<Button-1>', _start)
        self.mycanvas.tag_bind(item, '<B1-Motion>', _drag)
        # 右键旋转（B3）
        self.mycanvas.tag_bind(item, '<Button-3>', _rot_start)
        self.mycanvas.tag_bind(item, '<B3-Motion>', _rot_drag)

        # 遮罩位于指针之下
        try:
            self.mycanvas.tag_lower(item, self.hand1)
        except Exception:
            pass

    def record_preset_reached(self, preset_value):
        """记录到达预设点的历史数据"""
        if preset_value != self.last_reached_preset:
            self.preset_counter += 1
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.history_data.append((self.preset_counter, preset_value, timestamp))
            self.last_reached_preset = preset_value

            # 限制历史数据数量
            if len(self.history_data) > 100:
                self.history_data.pop(0)

            print(f"预设点到达记录: #{self.preset_counter} - 位置 {preset_value:.4f} - 时间 {timestamp}")

    def notify_displacement_change(self):
        """外部位移变化信号通知：仅在位移触发模式且处于预设点暂停时才恢复。"""
        try:
            if getattr(self, 'trigger_mode', 'time') == 'displacement' and self.moving_to_preset:
                # 隐藏备用继续按钮
                try:
                    self.mycanvas.coords(self.disp_continue_window, -1200, -1200)
                except Exception:
                    pass
                self.resume_movement()
        except Exception:
            pass

    def start(self):
        if not self.running:
            self.running = True
            # 初始化预设点遍历逻辑
            if self.preset_positions:
                # 找到下一个要到达的预设点
                self.find_next_preset_target()
                self.preset_cycle_complete = False

            # 运行时简化界面：只显示数字指示器和Stop按钮
            self.mycanvas.coords(self.mystartwindow, -1000, -1000)
            self.mycanvas.coords(self.myresetwindow, -1200, -1200)

            # 隐藏所有控制组件，只保留Stop按钮和数字指示器
            self.mycanvas.coords(self.speed_label_window, -1200, -1200)
            self.mycanvas.coords(self.speed_scale_window, -1200, -1200)
            self.mycanvas.coords(self.preset_button_window, -1200, -1200)
            if hasattr(self, 'horizontal_tilt_button_window'):
                self.mycanvas.coords(self.horizontal_tilt_button_window, -1200, -1200)
            self.mycanvas.coords(self.position_label_window, -1200, -1200)
            self.mycanvas.coords(self.position_info_window, -1200, -1200)
            self.mycanvas.coords(self.status_detail_window, -1200, -1200)
            self.mycanvas.coords(self.history_button_window, -1200, -1200)
            self.mycanvas.coords(self.mirror_button_window, -1200, -1200)
            self.mycanvas.coords(self.pointer_toggle_button_window, -1200, -1200)
            # 隐藏中心偏移和遮罩按钮
            try:
                self.mycanvas.coords(self.defect_center_button_window, -1200, -1200)
                self.mycanvas.coords(self.mask_button_window, -1200, -1200)
            except Exception:
                pass

            # 确保数字指示器保持可见（不隐藏indicator）
            print("运行时界面简化：只显示数字指示器和Stop按钮")
            self.update()

    def find_next_preset_target(self):
        """找到下一个要到达的预设点（支持乱序；方向由相邻两点大小关系决定）"""
        if not self.preset_positions:
            return
        # 若当前位置在列表之外，先定位到离当前位置最近的索引
        if self.target_preset_index < 0 or self.target_preset_index >= len(self.preset_positions):
            self.target_preset_index = 0
        # 按列表顺序遍历，不再强制按数值排序
        # 保持现有 target_preset_index，不做跳跃
    def stop(self):
        """手动停止运行"""
        self.running = False
        self.moving_to_preset = False  # 重置移动状态
        self.restore_all_controls()  # 恢复所有控制按钮

    def stop_after_cycle_complete(self):
        """循环完成后自动停止"""
        self.running = False
        self.moving_to_preset = False  # 重置移动状态
        self.restore_all_controls()  # 恢复所有控制按钮
        print("预设点循环完成，所有控制按钮已恢复显示")

    def restore_all_controls(self):
        """恢复显示所有控制组件 - 调用统一布局，确保顺序固定"""
        try:
            self._layout_buttons_centered()
        except Exception:
            # 兜底：如果统一布局不可用，保持原三行顺序
            py0 = int(self.canvaslength + 20*self.ui_scale)
            cx = int(self.centerx)
            dx = int(120*self.ui_scale)
            self.mycanvas.coords(self.mystartwindow, cx-dx, py0 + int(30*self.ui_scale))
            self.mycanvas.coords(self.mystopwindow,  cx,   py0 + int(30*self.ui_scale))
            self.mycanvas.coords(self.myresetwindow, cx+dx, py0 + int(30*self.ui_scale))
            self.mycanvas.coords(self.history_button_window, cx-dx, py0 + int(80*self.ui_scale))
            self.mycanvas.coords(self.mirror_button_window,  cx,    py0 + int(80*self.ui_scale))
            self.mycanvas.coords(self.pointer_toggle_button_window, cx+dx, py0 + int(80*self.ui_scale))
            try:
                self.mycanvas.coords(self.defect_center_button_window, cx-dx, py0 + int(130*self.ui_scale))
                self.mycanvas.coords(self.mask_button_window,          cx,    py0 + int(130*self.ui_scale))
            except Exception:
                pass
            below_y = py0 + int(170*self.ui_scale)
            self.mycanvas.coords(self.speed_label_window, int(120*self.ui_scale), below_y + int(0*self.ui_scale))
            self.mycanvas.coords(self.speed_scale_window, int(120*self.ui_scale), below_y + int(30*self.ui_scale))
            self.mycanvas.coords(self.preset_button_window, int(520*self.ui_scale), below_y + int(20*self.ui_scale))
            self.mycanvas.coords(self.position_label_window, int(520*self.ui_scale), below_y + int(0*self.ui_scale))
            self.mycanvas.coords(self.position_info_window, int(520*self.ui_scale), below_y + int(15*self.ui_scale))
            self.mycanvas.coords(self.status_detail_window, int(520*self.ui_scale), below_y + int(35*self.ui_scale))
            if hasattr(self, 'horizontal_tilt_button_window'):
                self.mycanvas.coords(self.horizontal_tilt_button_window, int(520*self.ui_scale), below_y + int(60*self.ui_scale))

    def reset(self):
        self.lengthofmeas=0
        self.current_position_index = 0  # 重置位置索引
        self.moving_to_preset = False  # 重置移动状态
        self.target_preset = None
        self.target_preset_index = 0  # 重置预设点索引
        self.preset_cycle_complete = False  # 重置循环完成状态
        self.last_reached_preset = None  # 重置历史记录状态
        self.update_position_info()  # 更新位置信息显示
        # 数字与指针复位
        self.indicator.configure(text="{:.4f}".format(self.lengthofmeas))
        self.last_indicator_text = "{:.4f}".format(self.lengthofmeas)
        # 确保指针已创建，然后同时复位主/副指针及其针尖线，避免残留形成“重影/两条线”
        try:
            self.ensure_pointers_created()
            self.mycanvas.coords(self.hand1, *self.coordinate_tip_line_A1())
            self.mycanvas.coords(self.hand2, *self.coordinate_tip_line_A2())
            if hasattr(self, 'hand1_tip'):
                self.mycanvas.coords(self.hand1_tip, *self.coordinate_tip_line_A1())
            if hasattr(self, 'hand2_tip'):
                self.mycanvas.coords(self.hand2_tip, *self.coordinate_tip_line_A2())
        except Exception:
            pass



    def update_speed(self, value):
        """更新指针移动速度 - 直接使用滑块值作为间隔时间"""
        speed_value = int(value)
        # 直接使用滑块值作为时间间隔（毫秒）
        # 滑块值越小 → 间隔越短 → 速度越快
        # 滑块值越大 → 间隔越长 → 速度越慢
        self.pauseduration[0] = speed_value

        print(f"速度设置: 滑块值{speed_value} -> 间隔: {self.pauseduration[0]}ms (值越小越快)")

    def open_preset_manager(self):
        """打开预设位置管理窗口"""
        preset_window = tk.Toplevel(self)
        preset_window.title("预设位置管理")
        preset_window.geometry("400x500")
        preset_window.resizable(False, False)

        # 当前预设位置列表
        tk.Label(preset_window, text="当前预设位置:", font=("Arial", 12, "bold")).pack(pady=10)

        # 列表框显示当前预设位置
        listbox_frame = tk.Frame(preset_window)
        listbox_frame.pack(pady=5, padx=20, fill=tk.BOTH, expand=True)

        self.preset_listbox = tk.Listbox(listbox_frame, height=8)
        scrollbar = tk.Scrollbar(listbox_frame, orient=tk.VERTICAL)
        self.preset_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.preset_listbox.yview)

        self.preset_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.update_preset_listbox()

        # 添加新预设位置
        add_frame = tk.Frame(preset_window)
        add_frame.pack(pady=10, padx=20, fill=tk.X)

        tk.Label(add_frame, text="新预设位置:").pack(side=tk.LEFT)
        self.new_preset_entry = tk.Entry(add_frame, width=10)
        self.new_preset_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(add_frame, text="添加", command=self.add_preset).pack(side=tk.LEFT, padx=5)

        # 操作按钮
        button_frame = tk.Frame(preset_window)
        # 触发模式设置
        trigger_frame = tk.Frame(preset_window)
        trigger_frame.pack(pady=5, padx=20, fill=tk.X)

        mode_text = "时间触发" if getattr(self, 'trigger_mode', 'time') == 'time' else "位移触发"
        mode_label = tk.Label(trigger_frame, text=f"当前模式: {mode_text}")
        mode_label.pack(side=tk.LEFT)

        def _toggle_trigger_mode():
            self.trigger_mode = 'displacement' if self.trigger_mode == 'time' else 'time'
            mode_label.config(text=f"当前模式: {'时间触发' if self.trigger_mode == 'time' else '位移触发'}")
            if self.trigger_mode == 'displacement':
                self._sensor_start()
            else:
                self._sensor_stop()

        tk.Button(trigger_frame, text="切换触发模式", command=_toggle_trigger_mode).pack(side=tk.LEFT, padx=10)

        # 位移变化阈值
        threshold_frame = tk.Frame(preset_window)
        threshold_frame.pack(pady=5, padx=20, fill=tk.X)
        tk.Label(threshold_frame, text="位移变化阈值(mm):").pack(side=tk.LEFT)
        threshold_var = tk.StringVar(value=str(self.sensor_threshold))
        threshold_entry = tk.Entry(threshold_frame, textvariable=threshold_var, width=8)
        threshold_entry.pack(side=tk.LEFT, padx=5)
        def _apply_threshold():
            try:
                v = float(threshold_var.get())
                if v <= 0:
                    raise ValueError
                self.sensor_threshold = v
            except Exception:
                try:
                    tk.messagebox.showwarning("阈值无效", "请输入大于0的数值，例如 0.01")
                except Exception:
                    pass
                threshold_var.set(str(self.sensor_threshold))
        tk.Button(threshold_frame, text="应用", command=_apply_threshold).pack(side=tk.LEFT, padx=5)
        # 静止判定参数
        still_frame = tk.Frame(preset_window)
        still_frame.pack(pady=5, padx=20, fill=tk.X)
        tk.Label(still_frame, text="静止判定阈值(mm):").pack(side=tk.LEFT)
        still_thr_var = tk.StringVar(value=str(self.still_threshold))
        tk.Entry(still_frame, textvariable=still_thr_var, width=8).pack(side=tk.LEFT, padx=5)
        tk.Label(still_frame, text="静止确认次数N:").pack(side=tk.LEFT, padx=10)
        still_cnt_var = tk.StringVar(value=str(self.still_confirm_count))
        tk.Entry(still_frame, textvariable=still_cnt_var, width=6).pack(side=tk.LEFT, padx=5)

        def _apply_still_params():
            try:
                thr = float(still_thr_var.get()); cnt = int(still_cnt_var.get())
                if thr <= 0 or cnt <= 0:
                    raise ValueError
                self.still_threshold = thr
                self.still_confirm_count = cnt
            except Exception:
                try:
                    tk.messagebox.showwarning("参数无效", "请输入大于0的阈值与次数，例如 0.003 与 5")
                except Exception:
                    pass
                still_thr_var.set(str(self.still_threshold))
                still_cnt_var.set(str(self.still_confirm_count))
        tk.Button(still_frame, text="应用", command=_apply_still_params).pack(side=tk.LEFT, padx=8)


        # 传感器状态与读数
        self._ensure_sensor_vars()
        status_frame = tk.Frame(preset_window)
        status_frame.pack(pady=5, padx=20, fill=tk.X)
        tk.Label(status_frame, text="传感器状态:").pack(side=tk.LEFT)
        tk.Label(status_frame, textvariable=self._sensor_status_var, fg="#008000").pack(side=tk.LEFT, padx=5)
        tk.Label(status_frame, text="当前位移:").pack(side=tk.LEFT, padx=20)
        tk.Label(status_frame, textvariable=self._sensor_value_var).pack(side=tk.LEFT)

        # 若进入位移触发模式，确保启动监控
        tk.Label(status_frame, text="检测状态:").pack(side=tk.LEFT, padx=20)
        tk.Label(status_frame, textvariable=self._det_status_var).pack(side=tk.LEFT)

        if getattr(self, 'trigger_mode', 'time') == 'displacement':
            self._sensor_start()

        button_frame.pack(pady=10)

        tk.Button(button_frame, text="删除选中", command=self.delete_preset).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="清空全部", command=self.clear_presets).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="恢复默认", command=self.restore_default_presets).pack(side=tk.LEFT, padx=5)

        # 暂停设置
        pause_frame = tk.Frame(preset_window)
        pause_frame.pack(pady=10, padx=20, fill=tk.X)

        tk.Label(pause_frame, text="预设点暂停时长(秒):").pack(side=tk.LEFT)
        self.pause_duration_var = tk.StringVar(value=str(self.pause_duration/1000))
        pause_entry = tk.Entry(pause_frame, textvariable=self.pause_duration_var, width=8)
        pause_entry.pack(side=tk.LEFT, padx=5)
        tk.Button(pause_frame, text="应用", command=self.update_pause_duration).pack(side=tk.LEFT, padx=5)

        tk.Button(preset_window, text="关闭", command=preset_window.destroy).pack(pady=10)

    def update_preset_listbox(self):
        """更新预设位置列表框"""
        self.preset_listbox.delete(0, tk.END)
        for i, pos in enumerate(self.preset_positions):
            self.preset_listbox.insert(tk.END, f"{i+1}. {pos:.4f}")

    def add_preset(self):
        """添加新的预设位置 - 支持乱序和重复"""
        try:
            new_pos = float(self.new_preset_entry.get())
            if 0 <= new_pos <= self.rangeupperbound:
                # 允许重复位置，不再检查是否已存在
                self.preset_positions.append(new_pos)
                # 不再自动排序，保持用户添加的顺序
                self.update_preset_listbox()
                self.new_preset_entry.delete(0, tk.END)
                self.update_position_info()
                print(f"添加预设位置: {new_pos:.4f} (总数: {len(self.preset_positions)})")
            else:
                tk.messagebox.showerror("错误", f"位置必须在0到{self.rangeupperbound}之间!")
        except ValueError:
            tk.messagebox.showerror("错误", "请输入有效的数字!")

    def delete_preset(self):
        """删除选中的预设位置"""
        selection = self.preset_listbox.curselection()
        if selection:
            index = selection[0]
            if len(self.preset_positions) > 1:  # 至少保留一个预设位置
                del self.preset_positions[index]
                self.update_preset_listbox()
                self.current_position_index = 0  # 重置索引
                self.update_position_info()
            else:
                tk.messagebox.showwarning("警告", "至少需要保留一个预设位置!")
        else:
            tk.messagebox.showinfo("提示", "请先选择要删除的位置!")

    def clear_presets(self):
        """清空所有预设位置"""
        if tk.messagebox.askyesno("确认", "确定要清空所有预设位置吗?"):
            self.preset_positions = [0.0]  # 保留一个默认位置
            self.current_position_index = 0
            self.update_preset_listbox()
            self.update_position_info()

    def restore_default_presets(self):
        """恢复默认预设位置"""
        self.preset_positions = [0.5, 1.0, 1.5, 2.0]
        self.current_position_index = 0
        self.update_preset_listbox()
        self.update_position_info()

    def update_pause_duration(self):
        """更新暂停时长"""
        try:
            duration = float(self.pause_duration_var.get())
            if duration >= 0:
                self.pause_duration = int(duration * 1000)  # 转换为毫秒
                tk.messagebox.showinfo("成功", f"暂停时长已设置为{duration}秒")
            else:
                tk.messagebox.showerror("错误", "暂停时长不能为负数!")
        except ValueError:
            tk.messagebox.showerror("错误", "请输入有效的数字!")

    def update_position_info(self):
        """更新位置信息显示"""
        if self.preset_cycle_complete:
            self.position_info.config(text="Cycle Complete")
            self.status_detail_label.config(text="All presets reached")
        elif self.target_preset_index < len(self.preset_positions):
            current_target = self.preset_positions[self.target_preset_index]
            self.position_info.config(text=f"Target: {current_target:.1f}")
            if self.moving_to_preset:
                self.status_detail_label.config(text=f"Pausing at {current_target:.1f}")
            else:
                self.status_detail_label.config(text=f"Moving to {current_target:.1f}")
        else:
            self.position_info.config(text="Mode: Continuous")
            self.status_detail_label.config(text="Ready to start")



    def is_near_preset(self, current_value, tolerance=0.01):
        """检查当前值是否接近某个预设位置"""
        for preset in self.preset_positions:
            if abs(current_value - preset) <= tolerance:
                return preset
        return None

    def show_history(self):
        """显示预设点到达历史记录"""
        if not self.history_data:
            messagebox.showinfo("预设点历史", "暂无预设点到达记录\n\n说明：只有当指针到达预设位置点时才会记录数据")
            return

        # 创建新窗口显示历史数据
        history_window = tk.Toplevel(self.master)
        history_window.title("预设点到达历史")
        history_window.geometry("500x500")

        # 创建表格框架
        table_frame = tk.Frame(history_window)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 创建滚动条
        scrollbar = tk.Scrollbar(table_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 创建列表框显示数据
        listbox = tk.Listbox(table_frame, yscrollcommand=scrollbar.set, font=("Courier", 10))
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)

        # 添加表头
        listbox.insert(tk.END, f"{'序号':<6} {'预设点位置':<12} {'到达时间':<12}")
        listbox.insert(tk.END, "-" * 35)

        # 添加数据
        for seq, preset_value, timestamp in self.history_data:
            listbox.insert(tk.END, f"{seq:<6} {preset_value:<12.4f} {timestamp:<12}")

        # 按钮框架
        button_frame = tk.Frame(history_window)
        button_frame.pack(pady=10)

        # 添加保存按钮
        save_button = tk.Button(button_frame, text="保存到文件",
                               command=lambda: self.save_history_to_file(),
                               font=("Times New Roman", 10, "bold"))
        save_button.pack(side=tk.LEFT, padx=5)

        # 添加清空按钮
        clear_button = tk.Button(button_frame, text="清空历史",
                               command=lambda: self.clear_history_data(history_window),
                               font=("Times New Roman", 10, "bold"))
        clear_button.pack(side=tk.LEFT, padx=5)

    def save_history_to_file(self):
        """保存预设点到达历史数据到CSV文件"""
        if not self.history_data:
            messagebox.showwarning("警告", "没有数据可保存")
            return

        try:
            # 生成文件名（包含时间戳）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"preset_history_{timestamp}.csv"

            # 写入CSV文件
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['序号', '预设点位置', '到达时间'])  # 写入表头
                writer.writerows(self.history_data)  # 写入数据

            messagebox.showinfo("成功", f"预设点历史数据已保存到文件: {filename}")
        except Exception as e:
            messagebox.showerror("错误", f"保存文件时出错: {str(e)}")

    def clear_history_data(self, window):
        """清空历史数据"""
        if messagebox.askyesno("确认", "确定要清空所有预设点到达记录吗？"):
            self.history_data.clear()
            self.preset_counter = 0
            self.last_reached_preset = None
            messagebox.showinfo("成功", "历史数据已清空")
            window.destroy()

    def force_show_pointers_at_preset(self):
        """在预设点暂停时强制显示指针"""
        # 保存当前指针状态，以便恢复时使用
        self.pointers_visible_before_preset = self.pointers_visible

        # 强制显示指针
        self.pointers_visible = True
        self.pointer_toggle_button.config(text="🔒 Always Show", bg="#FFD700", activebackground="#E6C200")
        # 仅确保存在并设为可见
        self.ensure_pointers_created()
        try:
            for it in (self.hand1, self.hand2, getattr(self, 'hand1_tip', None), getattr(self, 'hand2_tip', None)):
                if it is not None:
                    self.mycanvas.itemconfigure(it, state='normal')
        except Exception:
            pass
        print("预设点暂停期间 - 指针强制显示（黑色）")

    def toggle_pointers(self):
        """切换指针显示/隐藏状态 - 在预设点暂停时强制显示"""
        # 检查是否在预设点暂停状态
        if hasattr(self, 'moving_to_preset') and self.moving_to_preset:
            # 在预设点暂停期间，不允许隐藏指针
            print("预设点暂停期间不允许隐藏指针")
            return
        else:
            # 正常运行时，允许切换显示状态
            self.pointers_visible = not self.pointers_visible

            if self.pointers_visible:
                # 显示指针
                self.pointer_toggle_button.config(text="👁 Hide Pointers", bg="#FFB6C1", activebackground="#FF91A4")
                # 仅确保存在并设为可见
                self.ensure_pointers_created()
                try:
                    for it in (self.hand1, self.hand2, getattr(self, 'hand1_tip', None), getattr(self, 'hand2_tip', None)):
                        if it is not None:
                            self.mycanvas.itemconfigure(it, state='normal')
                except Exception:
                    pass
            else:
                # 隐藏指针
                self.pointer_toggle_button.config(text="👁 Show Pointers", bg="#90EE90", activebackground="#7FDD7F")
                # 不删除，改为隐藏避免闪烁
                try:
                    for it in (getattr(self, 'hand1', None), getattr(self, 'hand2', None), getattr(self, 'hand1_tip', None), getattr(self, 'hand2_tip', None)):
                        if it is not None:
                            self.mycanvas.itemconfigure(it, state='hidden')
                except Exception:
                    pass

    def toggle_mirror(self):
        """切换镜像状态"""
        prev_running = bool(self.running)
        self.is_mirrored = not self.is_mirrored
        # 更新按钮文本显示当前状态
        if self.is_mirrored:
            self.mirror_button.config(text="🔄 Mirror ON", bg="#FFD700", activebackground="#E6C200")
        else:
            self.mirror_button.config(text="🔄 Mirror OFF", bg="#F0E68C", activebackground="#E6DA7A")

        # 清除画布上的所有绘制元素（除了控件窗口）
        self.mycanvas.delete("all")

        # 重新创建控件窗口 - 根据运行状态决定位置
        # 重新创建指示器窗口到固定位置（按缩放）
        self.indicatorwindow=self.mycanvas.create_window(int(400*self.ui_scale), int(580*self.ui_scale), window=self.indicator)

        if self.running:
            # 运行时：保持界面简化，只显示Stop按钮和数字指示器
            self.mystartwindow=self.mycanvas.create_window(-1000,-1000,window=self.mystart)
            py0 = int(self.canvaslength + 20*self.ui_scale)
            self.mystopwindow=self.mycanvas.create_window(int(420*self.ui_scale), py0 + int(20*self.ui_scale), window=self.mystop)
            self.myresetwindow=self.mycanvas.create_window(-1200,-1200,window=self.myreset)
            self.history_button_window=self.mycanvas.create_window(-1200,-1200,window=self.history_button)
            self.mirror_button_window=self.mycanvas.create_window(int(340*self.ui_scale), py0 + int(60*self.ui_scale), window=self.mirror_button)  # Mirror按钮保持可见
            self.pointer_toggle_button_window=self.mycanvas.create_window(-1200,-1200,window=self.pointer_toggle_button)
            self.preset_button_window=self.mycanvas.create_window(-1200,-1200,window=self.preset_button)
            self.horizontal_tilt_button_window=self.mycanvas.create_window(-1200,-1200,window=self.horizontal_tilt_button)
            self.speed_label_window=self.mycanvas.create_window(-1200,-1200,window=self.speed_label)
            self.speed_scale_window=self.mycanvas.create_window(-1200,-1200,window=self.speed_scale)
            self.position_label_window=self.mycanvas.create_window(-1200,-1200,window=self.position_label)
            self.position_info_window=self.mycanvas.create_window(-1200,-1200,window=self.position_info)
            self.status_detail_window=self.mycanvas.create_window(-1200,-1200,window=self.status_detail_label)
            print("镜像切换时保持运行界面简化")
            # 中心偏移/遮罩按钮运行时隐藏
            try:
                self.defect_center_button_window=self.mycanvas.create_window(-1200,-1200,window=self.defect_center_button)
                self.mask_button_window=self.mycanvas.create_window(-1200,-1200,window=self.mask_button)
            except Exception:
                pass
        else:
            # 停止时：显示所有控件后，统一调用居中排布，确保顺序稳定
            py0 = int(self.canvaslength + 20*self.ui_scale)
            cx = int(self.centerx); dx = int(120*self.ui_scale)
            self.mystartwindow=self.mycanvas.create_window(cx-dx, py0 + int(30*self.ui_scale), window=self.mystart)
            self.mystopwindow=self.mycanvas.create_window(cx,     py0 + int(30*self.ui_scale), window=self.mystop)
            self.myresetwindow=self.mycanvas.create_window(cx+dx, py0 + int(30*self.ui_scale), window=self.myreset)
            self.history_button_window=self.mycanvas.create_window(cx-dx, py0 + int(80*self.ui_scale), window=self.history_button)
            self.mirror_button_window=self.mycanvas.create_window(cx,     py0 + int(80*self.ui_scale), window=self.mirror_button)
            self.pointer_toggle_button_window=self.mycanvas.create_window(cx+dx, py0 + int(80*self.ui_scale), window=self.pointer_toggle_button)
            try:
                self.defect_center_button_window=self.mycanvas.create_window(cx-dx, py0 + int(130*self.ui_scale), window=self.defect_center_button)
                self.mask_button_window=self.mycanvas.create_window(cx,     py0 + int(130*self.ui_scale), window=self.mask_button)
            except Exception:
                pass
            self.speed_label_window=self.mycanvas.create_window(int(150*self.ui_scale), py0 + int(20*self.ui_scale), window=self.speed_label)
            self.speed_scale_window=self.mycanvas.create_window(int(150*self.ui_scale), py0 + int(50*self.ui_scale), window=self.speed_scale)
            self.preset_button_window=self.mycanvas.create_window(int(560*self.ui_scale), py0 + int(60*self.ui_scale), window=self.preset_button)
            self.horizontal_tilt_button_window=self.mycanvas.create_window(int(560*self.ui_scale), py0 + int(100*self.ui_scale), window=self.horizontal_tilt_button)
            self.position_label_window=self.mycanvas.create_window(int(570*self.ui_scale), py0 + int(20*self.ui_scale), window=self.position_label)
            self.position_info_window=self.mycanvas.create_window(int(570*self.ui_scale), py0 + int(40*self.ui_scale), window=self.position_info)
            self.status_detail_window=self.mycanvas.create_window(int(570*self.ui_scale), py0 + int(60*self.ui_scale), window=self.status_detail_label)
            try:
                self._layout_buttons_centered()
            except Exception:
                pass
            # 同步固定数字指示器位置
            try:
                self.mycanvas.coords(self.indicatorwindow, int(400*self.ui_scale), int(580*self.ui_scale))
            except Exception:
                pass

        # 重新绘制整个表盘，确保指针句柄重建，避免残影/重复
        self.drawbackground()
        # 若镜像时处于运行状态，立即更新一次指针坐标
        if prev_running and hasattr(self, 'hand1') and hasattr(self, 'hand2'):
            try:
                self.mycanvas.coords(self.hand1, self.coordinateofA1())
                self.mycanvas.coords(self.hand2, self.coordinateofA2())
            except Exception:
                pass

    def toggle_center_offset(self):
        """切换指针中心圆心偏移，并刷新重绘。"""
        self.center_offset_enabled = not self.center_offset_enabled
        try:
            if self.center_offset_enabled:
                messagebox.showinfo("中心偏移", "已启用中心偏移，并用不同颜色标注两个中心点")
        except Exception:
            pass
        # 重绘
        self.mycanvas.delete("all")
        self.indicatorwindow=self.mycanvas.create_window(int(400*self.ui_scale),int(580*self.ui_scale),window=self.indicator)
        py0 = int(self.canvaslength + 20*self.ui_scale)
        cx = int(self.centerx); dx = int(120*self.ui_scale)
        self.mystartwindow=self.mycanvas.create_window(cx-dx, py0 + int(30*self.ui_scale), window=self.mystart)
        self.mystopwindow=self.mycanvas.create_window(cx,     py0 + int(30*self.ui_scale), window=self.mystop)
        self.myresetwindow=self.mycanvas.create_window(cx+dx, py0 + int(30*self.ui_scale), window=self.myreset)
        self.history_button_window=self.mycanvas.create_window(cx-dx, py0 + int(80*self.ui_scale), window=self.history_button)
        self.mirror_button_window=self.mycanvas.create_window(cx,     py0 + int(80*self.ui_scale), window=self.mirror_button)
        self.pointer_toggle_button_window=self.mycanvas.create_window(cx+dx, py0 + int(80*self.ui_scale), window=self.pointer_toggle_button)
        self.speed_label_window=self.mycanvas.create_window(int(120*self.ui_scale), py0 + int(170*self.ui_scale), window=self.speed_label)
        self.speed_scale_window=self.mycanvas.create_window(int(120*self.ui_scale), py0 + int(200*self.ui_scale), window=self.speed_scale)
        self.preset_button_window=self.mycanvas.create_window(int(520*self.ui_scale), py0 + int(190*self.ui_scale), window=self.preset_button)
        self.horizontal_tilt_button_window=self.mycanvas.create_window(int(520*self.ui_scale), py0 + int(230*self.ui_scale), window=self.horizontal_tilt_button)
        self.position_label_window=self.mycanvas.create_window(int(520*self.ui_scale), py0 + int(170*self.ui_scale), window=self.position_label)
        self.position_info_window=self.mycanvas.create_window(int(520*self.ui_scale), py0 + int(185*self.ui_scale), window=self.position_info)
        self.status_detail_window=self.mycanvas.create_window(int(520*self.ui_scale), py0 + int(205*self.ui_scale), window=self.status_detail_label)
        self.defect_center_button_window=self.mycanvas.create_window(cx-dx, py0 + int(130*self.ui_scale), window=self.defect_center_button)
        try:
            self.mask_button_window=self.mycanvas.create_window(cx, py0 + int(130*self.ui_scale), window=self.mask_button)
        except Exception:
            pass
        # 统一调用中心对称排布，避免启用中心偏移后控件乱序
        try:
            self._layout_buttons_centered()
        except Exception:
            pass
        self.drawbackground()

    def open_missing_ticks_manager(self):
        """功能已移除"""
        try:
            messagebox.showinfo("提示", "缺失刻线功能已移除")
        except Exception:
            pass

    def _layout_buttons_centered(self):
        """将底部按钮按行以中心为轴对称、连续排布，避免重叠。"""
        cx = int(self.centerx)
        py0 = int(self.canvaslength + 20*self.ui_scale)
        step = int(120 * self.ui_scale)

        row1 = [getattr(self, 'mystartwindow', None), getattr(self, 'mystopwindow', None), getattr(self, 'myresetwindow', None)]
        row2 = [getattr(self, 'history_button_window', None), getattr(self, 'mirror_button_window', None), getattr(self, 'pointer_toggle_button_window', None)]
        row3 = [getattr(self, 'defect_center_button_window', None), getattr(self, 'mask_button_window', None), getattr(self, 'preset_button_window', None)]

        def place_row(row, y):
            xs = [cx - step, cx, cx + step]
            for win, x in zip(row, xs):
                if win:
                    try:
                        self.mycanvas.coords(win, x, y)
                    except Exception:
                        pass

        place_row(row1, py0 + int(30*self.ui_scale))
        place_row(row2, py0 + int(80*self.ui_scale))
        place_row(row3, py0 + int(130*self.ui_scale))

        # 左右侧的辅助信息区：速度控件在左，状态在右
        try:
            _dx = int(10*self.ui_scale)  # 微调像素
            self.mycanvas.coords(self.speed_label_window, cx - 2.6*step + _dx, py0 + int(20*self.ui_scale))
            self.mycanvas.coords(self.speed_scale_window, cx - 2.6*step + _dx, py0 + int(85*self.ui_scale))
        except Exception:
            pass
        try:
            _dx2 = int(10*self.ui_scale)
            self.mycanvas.coords(self.position_label_window, cx + 2.5*step - _dx2, py0 + int(20*self.ui_scale))
            self.mycanvas.coords(self.position_info_window, cx + 2.5*step - _dx2, py0 + int(55*self.ui_scale))
            self.mycanvas.coords(self.status_detail_window, cx + 2.5*step - _dx2, py0 + int(90*self.ui_scale))
        except Exception:
            pass

        try:
            if getattr(self, 'preset_button_window', None) and getattr(self, 'horizontal_tilt_button_window', None):
                coords = self.mycanvas.coords(self.preset_button_window)
                if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                    px, py = coords[0], coords[1]
                    self.mycanvas.coords(self.horizontal_tilt_button_window, px, py + int(40*self.ui_scale))
        except Exception:
            pass

if __name__ == "__main__":
    root=tk.Tk()
    #root.attributes('-fullscreen',True)
    root.title("主窗口")
    mygauge=dialgauge(root)
    mygauge.drawbackground()
    mygauge.showcavnas()
    mygauge.update()
    root.mainloop()