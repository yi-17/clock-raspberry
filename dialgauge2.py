from dialgauge import dialgauge
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass
import time
import random
import tkinter as tk
import tkinter.messagebox
import math as mt
import datetime


class dialgauge2(dialgauge):
    def __init__(self,master=None):
        super().__init__(master)
        # 本地缩放系数（相对父类基准800）
        scale = getattr(self, 'ui_scale', 1.0)

        # 千分表刻线 / 指针统一细化为 1 像素
        self.widthoftickA1 = 1
        self.widthoftickA2 = 1
        try:
            if hasattr(self, 'hand1'):
                self.mycanvas.itemconfigure(self.hand1, width=self.widthoftickA1)
            if hasattr(self, 'hand2'):
                self.mycanvas.itemconfigure(self.hand2, width=self.widthoftickA2)
            if hasattr(self, 'hand1_tip'):
                self.mycanvas.itemconfigure(self.hand1_tip, width=self.widthoftickA1)
            if hasattr(self, 'hand2_tip'):
                self.mycanvas.itemconfigure(self.hand2_tip, width=self.widthoftickA2)
        except Exception:
            pass

        self.numberofintervaloftickl=20 # the number of interval of long tick mark of A1
        self.numberofintervaloftickm=self.numberofintervaloftickl # the number of interval of middle tick mark of A1
        self.numberofintervalofticks=200 # the number of interval of short tick mark of A1
        self.numberofintervaloftickofA2=5 # the number of interval of tick mark of A2
        # 适配缩放的A2刻度长度
        _scale = getattr(self, 'ui_scale', 1.0)
        self.neftickmarkA2=self.radiusfdialA2-int(10*_scale) # the length from the near end of tick mark A2 to center of dial A2
        self.feftickmarkA2=self.radiusfdialA2-(-int(2*_scale))
        self.strofA1=(0,10,20,30,40,50,60,70,80,90,100,90,80,70,60,50,40,30,20,10)
        self.strofA2=("0",".2",".4",".6",".8","1.0")
        self.movelengthofA2center=self.canvaslength/6 # the distance scales with canvaslength (kept proportional)
        self.centerofarmA2x=self.centerx-0.5*self.movelengthofA2center # the x of center coordinate of A2
        self.centerofarmA2y=self.centery-self.movelengthofA2center # the y of center coordinate of A2
        self.intervaloftickl=1/self.numberofintervaloftickl # the interval of long tick mark
        self.intervaloftickm=1/self.numberofintervaloftickm # the interval of middle tick mark
        self.intervalofticks=1/self.numberofintervalofticks # the interval of short tick mark
        self.intervaloftickofA2=1/self.numberofintervaloftickofA2 # the interval of tick mark of A2
        self.lengthofmeas=float(0) #the initial length of measurand
        ########################################################################################################################
        self.increaseinterval=0.002  #增加步长以提供更平滑的移动
        self.rangeupperbound=10 # the range upper bound of dialgauge2, aligned with dialgauge (0-10)
        self.timeinterval=10 #define the time interval of the update function that means the speed of the hand travel (优化为更稳定的间隔)
        self.pausenumber=0 #define a varible to store the times the hand1 and hand2 running before pause

        # 指针显示控制（覆盖父类设置）
        self.pointers_visible = True  # 指针可见性标志
        self.pointers_visible_before_preset = True  # 预设点暂停前的指针状态

        # 预设位置跳转控制（覆盖父类设置）- 改为用户可自定义
        # 默认从小到大顺序，使用英文小数点与逗号，避免输入法导致的语法错误
        self.preset_positions = [
            0.001,0.04,0.13,0.07,0.08,0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45,
            0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00,
            1.01, 1.00, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.55, 0.50, 0.45, 0.40, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10, 0.05, 0.00
        ]
        self.current_position_index = 0  # 当前位置索引
        self.jump_mode = False  # 跳转模式标志
        # 移除continuous_mode，始终使用连续移动模式
        self.pause_at_presets = True  # 在预设点暂停
        self.pause_duration = 1000  # 暂停时长(毫秒)
        self.moving_to_preset = False  # 是否正在移动到预设点
        self.target_preset = None  # 目标预设点
        self.target_preset_index = 0  # 目标预设点索引
        self.preset_cycle_complete = False  # 预设点循环是否完成
        self.lengthtopause=(0.05,0.05) #define the step pause length to which length of dialgauge runing equals,
                      #\ the hand1 and hand2 should pause
        self.pauseduration=[1,1000] # the time duatrion of gauge pausing, the first element indicate the speed of hand moving, the
        self.gaugewaitingduration=1
        self.numberofpiecewise=1

        # 重新定义美化的按钮样式 (覆盖父类)
        button_style = {
            "font": ("Arial", 10, "bold"),
            "width": 10,
            "relief": tk.RAISED,
            "bd": 2,
            "bg": "#e6e6e6",
            "activebackground": "#d0d0d0"
        }

        # 美化的速度控制滑块 (在父类初始化后添加)
        self.speed_label=tk.Label(self,text="⚡ Speed Control:",
                                 font=("Arial", max(8,int(10*scale)), "bold"),
                                 bg="#f0f0f0",fg="#333333")
        self.speed_scale=tk.Scale(self, from_=1, to=200, orient=tk.HORIZONTAL, length=int(200*scale),
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

        # 指针显示控制按钮（覆盖父类）
        self.pointer_toggle_button=tk.Button(self,text="👁 Hide Pointers",command=self.toggle_pointers,**button_style)
        self.pointer_toggle_button.config(bg="#FFB6C1", activebackground="#FF91A4")  # 浅粉色

        # 预设位置管理组件（覆盖父类）
        self.preset_button=tk.Button(self,text="⚙ Presets",command=self.open_preset_manager,**button_style)
        self.preset_button.config(bg="#87CEEB", activebackground="#7BB8D6")  # 天蓝色

        self.position_label=tk.Label(self,text="📍 Status:",
                                    font=("Arial", max(8,int(10*scale)), "bold"),
                                    bg="#f0f0f0",fg="#333333")
        self.position_info=tk.Label(self,text=f"Mode: Continuous",
                                   font=("Arial", max(7,int(9*scale))),
                                   bg="#f0f0f0",fg="#666666")

        # 添加详细状态显示
        self.status_detail_label=tk.Label(self,text="Ready to start",
                                         font=("Arial", max(6,int(8*scale))),
                                         bg="#f0f0f0",fg="#888888")

        # 优化的布局 - 控件全部移至下方扩展面板
        # 指示器仍贴近表盘区域（若父类已创建，则先删除旧窗口再重建，避免重复）
        try:
            if hasattr(self, 'indicatorwindow') and self.indicatorwindow:
                self.mycanvas.delete(self.indicatorwindow)
        except Exception:
            pass
        self.indicatorwindow=self.mycanvas.create_window(int(400*scale),int(580*scale),window=self.indicator)

        panel_y0 = int(self.canvaslength + 20*scale)
        # 主控制按钮 - 以中心为轴对称
        cx = int(self.centerx)
        step = int(120*scale)
        for _attr in ('mystartwindow','mystopwindow','myresetwindow'):
            try:
                if hasattr(self, _attr) and getattr(self, _attr):
                    self.mycanvas.delete(getattr(self, _attr))
            except Exception:
                pass
        self.mystartwindow=self.mycanvas.create_window(cx-step, panel_y0 + int(30*scale), window=self.mystart)
        self.mystopwindow=self.mycanvas.create_window(cx, panel_y0 + int(30*scale), window=self.mystop)
        self.myresetwindow=self.mycanvas.create_window(cx+step, panel_y0 + int(30*scale), window=self.myreset)

        # 功能按钮 - 面板第二行
        for _attr in ('history_button_window','mirror_button_window','pointer_toggle_button_window'):
            try:
                if hasattr(self, _attr) and getattr(self, _attr):
                    self.mycanvas.delete(getattr(self, _attr))
            except Exception:
                pass
        self.history_button_window=self.mycanvas.create_window(cx-step, panel_y0 + int(80*scale), window=self.history_button)
        self.mirror_button_window=self.mycanvas.create_window(cx, panel_y0 + int(80*scale), window=self.mirror_button)
        self.pointer_toggle_button_window=self.mycanvas.create_window(cx+step, panel_y0 + int(80*scale), window=self.pointer_toggle_button)
        # 遮罩按钮
        self.mask_button=tk.Button(self,text="▦ Mask",command=self.add_mask_box,**button_style)
        self.mask_button.config(bg="#EEE8AA", activebackground="#E6DD8A")
        try:
            if hasattr(self, 'mask_button_window') and self.mask_button_window:
                self.mycanvas.delete(self.mask_button_window)
        except Exception:
            pass
        self.mask_button_window=self.mycanvas.create_window(cx, panel_y0 + int(130*scale), window=self.mask_button)
        self._mask_items=[]

        # 速度控制 - 面板左侧（微调到更靠左一点）
        _dx = int(10*scale)
        for _attr in ('speed_label_window','speed_scale_window'):
            try:
                if hasattr(self, _attr) and getattr(self, _attr):
                    self.mycanvas.delete(getattr(self, _attr))
            except Exception:
                pass
        # 与百分表一致：速度区更靠左，纵向留白更大
        self.speed_label_window=self.mycanvas.create_window(cx - int(2.6*step) + _dx, panel_y0 + int(20*scale), window=self.speed_label)
        self.speed_scale_window=self.mycanvas.create_window(cx - int(2.6*step) + _dx, panel_y0 + int(85*scale), window=self.speed_scale)

        # 预设位置管理控件 - 面板右侧（微调到更靠右一点）
        _dx2 = int(10*scale)
        for _attr in ('preset_button_window','position_label_window','position_info_window','status_detail_window'):
            try:
                if hasattr(self, _attr) and getattr(self, _attr):
                    self.mycanvas.delete(getattr(self, _attr))
            except Exception:
                pass
        self.preset_button_window=self.mycanvas.create_window(cx + 3*step - _dx2, panel_y0 + int(20*scale), window=self.preset_button)
        try:
            if hasattr(self, 'horizontal_tilt_button_window') and self.horizontal_tilt_button_window:
                self.mycanvas.delete(self.horizontal_tilt_button_window)
        except Exception:
            pass
        self.horizontal_tilt_button_window=self.mycanvas.create_window(cx + 3*step - _dx2, panel_y0 + int(60*scale), window=self.horizontal_tilt_button)
        # 与百分表一致：右侧灰色状态区位置
        self.position_label_window=self.mycanvas.create_window(cx + int(2.5*step) - _dx2, panel_y0 + int(20*scale), window=self.position_label)
        self.position_info_window=self.mycanvas.create_window(cx + int(2.5*step) - _dx2, panel_y0 + int(55*scale), window=self.position_info)
        self.status_detail_window=self.mycanvas.create_window(cx + int(2.5*step) - _dx2, panel_y0 + int(90*scale), window=self.status_detail_label)

        # 缺陷按钮：仅中心偏移
        self.defect_center_button=tk.Button(self,text="⚠ Center Offset",command=self.toggle_center_offset,**button_style)
        self.defect_center_button.config(bg="#FFA07A", activebackground="#FF8C69")
        try:
            if hasattr(self, 'defect_center_button_window') and self.defect_center_button_window:
                self.mycanvas.delete(self.defect_center_button_window)
        except Exception:
            pass
        self.defect_center_button_window=self.mycanvas.create_window(cx-step, panel_y0 + int(130*scale), window=self.defect_center_button)
        # 位移触发备用继续按钮
        self.disp_continue_btn=tk.Button(self,text="▶ Continue",command=self.notify_displacement_change,**button_style)
        self.disp_continue_btn.config(bg="#ADD8E6", activebackground="#9AC7D7")
        try:
            if hasattr(self, 'disp_continue_window') and self.disp_continue_window:
                self.mycanvas.delete(self.disp_continue_window)
        except Exception:
            pass
        self.disp_continue_window=self.mycanvas.create_window(cx+step, panel_y0 + int(130*scale), window=self.disp_continue_btn)
        self.mycanvas.coords(self.disp_continue_window, -1200, -1200)

        # 统一一次中心对称排布，避免不同初始化路径产生差异
        try:
            self._layout_buttons_centered()
        except Exception:
            pass


    def drawcirclebofA2(self) :#draw the circle boundary of dial A2
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
        self.mycanvas.create_arc(bbox,start=0, extent=180, style=tk.ARC,width=self.widthofdialA2, tags=('dial_static',))
        
    # 覆盖父类中心端点的外观以显示黑圈中间白点（A1/A2均继承父类实现即可）

    def drawtickofA2(self):
        for i in range(self.numberofintervaloftickofA2):
            # 副表盘使用半圆弧设计，从左到右分布（0到π）
            angle = i * self.intervaloftickofA2 * mt.pi

            # 确定表盘中心位置
            if self.is_mirrored:
                center_x = 2*self.centerx - self.centerofarmA2x
                center_y = self.centerofarmA2y
            else:
                center_x = self.centerofarmA2x
                center_y = self.centerofarmA2y

            x1 = center_x + self.neftickmarkA2 * mt.cos(angle)
            y1 = center_y - self.neftickmarkA2 * mt.sin(angle)  # 注意y轴方向
            x2 = center_x + self.feftickmarkA2 * mt.cos(angle)
            y2 = center_y - self.feftickmarkA2 * mt.sin(angle)  # 注意y轴方向

            vectoroftickofA2=self._apply_tilt_to_coords((x1, y1, x2, y2))
            self.mycanvas.create_line(vectoroftickofA2,width=self.widthoftickA2,smooth=True, tags=('dial_static',) )

        # 额外的刻度线（第6个刻度，对应1.0）
        angle_sup = 5 * self.intervaloftickofA2 * mt.pi
        # 始终绘制

        if self.is_mirrored:
            center_x_sup = 2*self.centerx - self.centerofarmA2x
            center_y_sup = self.centerofarmA2y
        else:
            center_x_sup = self.centerofarmA2x
            center_y_sup = self.centerofarmA2y

        x1_sup = center_x_sup + self.neftickmarkA2 * mt.cos(angle_sup)
        y1_sup = center_y_sup - self.neftickmarkA2 * mt.sin(angle_sup)
        x2_sup = center_x_sup + self.feftickmarkA2 * mt.cos(angle_sup)
        y2_sup = center_y_sup - self.feftickmarkA2 * mt.sin(angle_sup)

        vectoroftickofA2sup=self._apply_tilt_to_coords((x1_sup, y1_sup, x2_sup, y2_sup))
        self.mycanvas.create_line(vectoroftickofA2sup,width=self.widthoftickA2,smooth=True, tags=('dial_static',) )

    def drawnumberofA2(self):
        for i in range(self.numberofintervaloftickofA2): #draw the number of dial A2 start position is 0 degree
            # 副表盘使用半圆弧设计，从左到右分布（0到π）
            angle = i * self.intervaloftickofA2 * mt.pi

            # 确定表盘中心位置
            if self.is_mirrored:
                center_x = 2*self.centerx - self.centerofarmA2x
                center_y = self.centerofarmA2y
            else:
                center_x = self.centerofarmA2x
                center_y = self.centerofarmA2y

            x = center_x + self.lengthofnumberA2 * mt.cos(angle)
            y = center_y - self.lengthofnumberA2 * mt.sin(angle)  # 注意y轴方向

            # 使用镜像文字方法
            self.create_mirrored_text(x, y, str(self.strofA2[i]),
                                    ("Times New Roman", int(10/500*self.canvaslength), "bold"))

        # 额外的数字（第6个数字，对应1.0）
        angle_extra = 5 * self.intervaloftickofA2 * mt.pi

        if self.is_mirrored:
            center_x_extra = 2*self.centerx - self.centerofarmA2x
            center_y_extra = self.centerofarmA2y
        else:
            center_x_extra = self.centerofarmA2x
            center_y_extra = self.centerofarmA2y

        _scale = getattr(self, 'ui_scale', 1.0)
        x_extra = center_x_extra + (self.lengthofnumberA2-int(3*_scale)) * mt.cos(angle_extra)
        y_extra = center_y_extra - (self.lengthofnumberA2-int(3*_scale)) * mt.sin(angle_extra)

        # 使用镜像文字方法
        self.create_mirrored_text(x_extra, y_extra, str(self.strofA2[5]),
                                ("Times New Roman", int(10/500*self.canvaslength), "bold"))

    def coordinateofA1(self): #compute the coordinates of hand A1 for trangle shape hand
        integer_part=int(self.lengthofmeas)
        fractional_part=round(self.lengthofmeas-integer_part,3)/2
        # 应用中心偏移（沿用父类字段）
        x0 = self.centerx + (self.center_offset_dx if getattr(self, 'center_offset_enabled', False) else 0)
        y0 = self.centery + (self.center_offset_dy if getattr(self, 'center_offset_enabled', False) else 0)
        adjustangle=(1/4)*mt.pi #for create the hand1's shape as triangle
        angle=fractional_part*(10*2*mt.pi)

        # 缓存常用计算 - 更细的指针
        radiust=6/500*self.canvaslength  # 减小指针底部宽度
        # A1针尖长度与主盘长刻度外端一致，确保重合
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

    # 叠加针尖细线（与刻线等宽）
    def coordinate_tip_line_A1(self):
        integer_part=int(self.lengthofmeas)
        fractional_part=round(self.lengthofmeas-integer_part,3)/2
        x0 = self.centerx + (self.center_offset_dx if getattr(self, 'center_offset_enabled', False) else 0)
        y0 = self.centery + (self.center_offset_dy if getattr(self, 'center_offset_enabled', False) else 0)
        base_angle = (fractional_part*(10*2*mt.pi)+self.phasedelaytozero) if self.is_mirrored else (-(fractional_part*(10*2*mt.pi))+self.phasedelaytozero)
        x_tip = x0 + float(self.feftickmarkl)*mt.cos(base_angle)
        y_tip = y0 - float(self.feftickmarkl)*mt.sin(base_angle)
        # 整数网格量化，确保与中心小白点对齐（结合直端帽）
        quantized = (round(x0), round(y0), round(x_tip), round(y_tip))
        return self._apply_tilt_to_coords(quantized)

    def coordinateA2ini(self):
        # 确定A2表盘中心位置
        if self.is_mirrored:
            x0 = 2*self.centerx - self.centerofarmA2x
            y0 = self.centerofarmA2y
        else:
            x0 = self.centerofarmA2x
            y0 = self.centerofarmA2y

        # 初始指针角度为0（指向右侧）
        base_angle = 0
        adjustangle = (1/20) * mt.pi
        radiust = 12/500 * self.canvaslength  # 更细的副表盘指针
        # A2初始针尖长度与A2刻度外端一致
        radiush = float(self.feftickmarkA2)

        # 计算指针的三个顶点坐标
        x1 = x0 - radiust * mt.cos(base_angle - adjustangle)
        y1 = y0 + radiust * mt.sin(base_angle - adjustangle)
        x2 = x0 - radiust * mt.cos(base_angle + adjustangle)
        y2 = y0 + radiust * mt.sin(base_angle + adjustangle)
        x3 = x0 + radiush * mt.cos(base_angle)
        y3 = y0 - radiush * mt.sin(base_angle)

        return self._apply_tilt_to_coords((x1,y1,x2,y2,x3,y3))

    def coordinateofA2(self):
        # 使用 dialgauge 的上限：0 ~ self.rangeupperbound 映射到半圆 [0, π]
        if self.lengthofmeas > self.rangeupperbound:
            print("the lenght overflow")
        else:
            # 确定A2表盘中心位置
            if self.is_mirrored:
                x0 = 2*self.centerx - self.centerofarmA2x
                y0 = self.centerofarmA2y
            else:
                x0 = self.centerofarmA2x
                y0 = self.centerofarmA2y

            # 归一化到 [0,1]
            normalized = max(0.0, min(1.0, self.lengthofmeas / self.rangeupperbound))
            # 镜像时反向映射，保持与百分表一致的“反转”直观效果
            if self.is_mirrored:
                base_angle = (1.0 - normalized) * mt.pi
            else:
                base_angle = normalized * mt.pi

            adjustangle = (1/20) * mt.pi
            radiust = 12/500 * self.canvaslength  # 更细的副表盘指针
            # A2针尖长度与A2刻度外端一致
            radiush = float(self.feftickmarkA2)

            # 计算指针的三个顶点坐标
            x1 = x0 - radiust * mt.cos(base_angle - adjustangle)
            y1 = y0 + radiust * mt.sin(base_angle - adjustangle)
            x2 = x0 - radiust * mt.cos(base_angle + adjustangle)
            y2 = y0 + radiust * mt.sin(base_angle + adjustangle)
            x3 = x0 + radiush * mt.cos(base_angle)
            y3 = y0 - radiush * mt.sin(base_angle)
            return self._apply_tilt_to_coords((x1,y1,x2,y2,x3,y3))

    def coordinate_tip_line_A2(self):
        if self.is_mirrored:
            x0 = 2*self.centerx - self.centerofarmA2x
            normalized = max(0.0, min(1.0, self.lengthofmeas / self.rangeupperbound))
            base_angle = (1.0 - normalized) * mt.pi
        else:
            x0 = self.centerofarmA2x
            normalized = max(0.0, min(1.0, self.lengthofmeas / self.rangeupperbound))
            base_angle = normalized * mt.pi
        y0 = self.centerofarmA2y
        x_tip = x0 + float(self.feftickmarkA2)*mt.cos(base_angle)
        y_tip = y0 - float(self.feftickmarkA2)*mt.sin(base_angle)
        quantized = (round(x0), round(y0), round(x_tip), round(y_tip))
        return self._apply_tilt_to_coords(quantized)

    def update_speed(self, value):
        """更新指针移动速度 - 直接使用滑块值作为间隔时间（覆盖父类）"""
        # 运行时忽略速度调整，防止滑块在隐藏状态下仍然响应
        if hasattr(self, 'running') and self.running:
            print(f"运行时忽略速度调整: {value}")
            return

        speed_value = int(value)
        # 直接使用滑块值作为时间间隔（毫秒）
        # 滑块值越小 → 间隔越短 → 速度越快
        # 滑块值越大 → 间隔越长 → 速度越慢
        self.pauseduration[0] = speed_value

        print(f"速度设置: 滑块值{speed_value} -> 间隔: {self.pauseduration[0]}ms (值越小越快)")

    def open_preset_manager(self):
        """打开预设位置管理窗口（覆盖父类方法以适应dialgauge2的范围）"""
        preset_window = tk.Toplevel(self)
        preset_window.title("预设位置管理 - Dial Gauge 2")
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
                if thr <= 0 or cnt <= 0: raise ValueError
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

        # 若当前是位移触发，确保启动监控
        tk.Label(status_frame, text="检测状态:").pack(side=tk.LEFT, padx=20)
        tk.Label(status_frame, textvariable=self._det_status_var).pack(side=tk.LEFT)

        if getattr(self, 'trigger_mode', 'time') == 'displacement':
            self._sensor_start()

        tk.Button(preset_window, text="关闭", command=preset_window.destroy).pack(pady=10)

    def restore_default_presets(self):
        """恢复默认预设位置（覆盖父类以适应dialgauge2范围）- 支持乱序和重复"""
        # 恢复为从小到大的顺序
        self.preset_positions = [
            0.00,0.05,0.10,0.15,0.20,0.25,0.30,0.35,0.40,0.45,
            0.50,0.55,0.60,0.65,0.70,0.75,0.80,0.85,0.90,0.95,1.00,1.01,1.00
        ]
        self.current_position_index = 0
        self.update_preset_listbox()
        self.update_position_info()

    def toggle_pointers(self):
        """切换指针显示/隐藏状态 - 覆盖父类以确保正确的状态管理"""
        # 检查是否在预设点暂停状态
        if hasattr(self, 'moving_to_preset') and self.moving_to_preset:
            # 在预设点暂停期间，不允许隐藏指针
            print("预设点暂停期间不允许隐藏指针")
            return
        else:
            # 正常运行时，允许切换显示状态
            self.pointers_visible = not self.pointers_visible

            if self.pointers_visible:
                # 显示指针（统一外观：红色、宽度2，并加针尖细线与刻线等宽）
                self.pointer_toggle_button.config(text="👁 Hide Pointers", bg="#FFB6C1", activebackground="#FF91A4")
                self.ensure_pointers_created()
                try:
                    for it in (self.hand1, self.hand2, getattr(self, 'hand1_tip', None), getattr(self, 'hand2_tip', None)):
                        if it is not None:
                            self.mycanvas.itemconfigure(it, state='normal')
                except Exception:
                    pass
                print("指针已显示")
            else:
                # 隐藏指针：同时移除叠加线
                self.pointer_toggle_button.config(text="👁 Show Pointers", bg="#90EE90", activebackground="#7FDD7F")
                try:
                    for it in (getattr(self, 'hand1', None), getattr(self, 'hand2', None), getattr(self, 'hand1_tip', None), getattr(self, 'hand2_tip', None)):
                        if it is not None:
                            self.mycanvas.itemconfigure(it, state='hidden')
                except Exception:
                    pass
                print("指针已隐藏")

    def force_show_pointers_at_preset(self):
        """在预设点暂停时强制显示指针 - 覆盖父类以确保正确的颜色"""
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

    def resume_movement(self):
        """恢复移动（暂停结束后调用）- 覆盖父类以确保正确的状态恢复"""
        self.moving_to_preset = False
        self.target_preset = None

        # 恢复预设点暂停前的指针状态
        self.pointers_visible = self.pointers_visible_before_preset

        if self.pointers_visible:
            # 恢复显示状态
            self.pointer_toggle_button.config(text="👁 Hide Pointers", bg="#FFB6C1", activebackground="#FF91A4")
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
            try:
                for it in (getattr(self, 'hand1', None), getattr(self, 'hand2', None), getattr(self, 'hand1_tip', None), getattr(self, 'hand2_tip', None)):
                    if it is not None:
                        self.mycanvas.itemconfigure(it, state='hidden')
            except Exception:
                pass
            print("恢复指针隐藏状态")

        # 移动到下一个预设点
        self.target_preset_index += 1
        self.update_position_info()

    def toggle_mirror(self):
        """切换镜像状态 - 完整视觉镜像"""
        prev_running = bool(self.running)
        self.is_mirrored = not self.is_mirrored
        scale = getattr(self, 'ui_scale', 1.0)
        # 更新按钮文本显示当前状态
        if self.is_mirrored:
            self.mirror_button.config(text="🔄 Mirror ON", bg="#FFD700", activebackground="#E6C200")
        else:
            self.mirror_button.config(text="🔄 Mirror OFF", bg="#F0E68C", activebackground="#E6DA7A")

        # 清除画布上的所有绘制元素（除了控件窗口）
        self.mycanvas.delete("all")

        # 重新创建控件窗口 - 根据运行状态决定位置
        self.indicatorwindow=self.mycanvas.create_window(int(400*scale),int(580*scale),window=self.indicator)

        if self.running:
            # 运行时：保持界面简化，只显示Stop按钮和数字指示器（完全按照父类逻辑）
            self.mystartwindow=self.mycanvas.create_window(-1000,-1000,window=self.mystart)
            panel_y0 = int(self.canvaslength + 20*scale)
            self.mystopwindow=self.mycanvas.create_window(int(420*scale), panel_y0 + int(20*scale), window=self.mystop)
            self.myresetwindow=self.mycanvas.create_window(-1200,-1200,window=self.myreset)
            self.history_button_window=self.mycanvas.create_window(-1200,-1200,window=self.history_button)
            self.mirror_button_window=self.mycanvas.create_window(-1200,-1200,window=self.mirror_button)
            self.pointer_toggle_button_window=self.mycanvas.create_window(-1200,-1200,window=self.pointer_toggle_button)
            self.preset_button_window=self.mycanvas.create_window(-1200,-1200,window=self.preset_button)
            self.horizontal_tilt_button_window=self.mycanvas.create_window(-1200,-1200,window=self.horizontal_tilt_button)
            self.speed_label_window=self.mycanvas.create_window(-1200,-1200,window=self.speed_label)
            self.speed_scale_window=self.mycanvas.create_window(-1200,-1200,window=self.speed_scale)
            self.position_label_window=self.mycanvas.create_window(-1200,-1200,window=self.position_label)
            self.position_info_window=self.mycanvas.create_window(-1200,-1200,window=self.position_info)
            self.status_detail_window=self.mycanvas.create_window(-1200,-1200,window=self.status_detail_label)
            print("镜像切换时保持运行界面简化")
            # 新增按钮运行时隐藏
            try:
                self.defect_center_button_window=self.mycanvas.create_window(-1200,-1200,window=self.defect_center_button)
                self.mask_button_window=self.mycanvas.create_window(-1200,-1200,window=self.mask_button)
            except Exception:
                pass
        else:
            # 停止时：显示所有控件
            panel_y0 = int(self.canvaslength + 20*scale)
            self.mystartwindow=self.mycanvas.create_window(int(320*scale), panel_y0 + int(20*scale), window=self.mystart)
            self.mystopwindow=self.mycanvas.create_window(int(420*scale), panel_y0 + int(20*scale), window=self.mystop)
            self.myresetwindow=self.mycanvas.create_window(int(520*scale), panel_y0 + int(20*scale), window=self.myreset)
            self.history_button_window=self.mycanvas.create_window(int(250*scale), panel_y0 + int(60*scale), window=self.history_button)
            self.mirror_button_window=self.mycanvas.create_window(int(340*scale), panel_y0 + int(60*scale), window=self.mirror_button)
            self.pointer_toggle_button_window=self.mycanvas.create_window(int(450*scale), panel_y0 + int(60*scale), window=self.pointer_toggle_button)
            self.preset_button_window=self.mycanvas.create_window(int(560*scale), panel_y0 + int(60*scale), window=self.preset_button)
            self.horizontal_tilt_button_window=self.mycanvas.create_window(int(560*scale), panel_y0 + int(100*scale), window=self.horizontal_tilt_button)
            self.speed_label_window=self.mycanvas.create_window(int(150*scale), panel_y0 + int(20*scale), window=self.speed_label)
            self.speed_scale_window=self.mycanvas.create_window(int(150*scale), panel_y0 + int(50*scale), window=self.speed_scale)
            self.position_label_window=self.mycanvas.create_window(int(570*scale), panel_y0 + int(20*scale), window=self.position_label)
            self.position_info_window=self.mycanvas.create_window(int(570*scale), panel_y0 + int(40*scale), window=self.position_info)
            self.status_detail_window=self.mycanvas.create_window(int(570*scale), panel_y0 + int(60*scale), window=self.status_detail_label)
            # 新增按钮停止时显示
            try:
                self.defect_center_button_window=self.mycanvas.create_window(int(250*scale), panel_y0 + int(100*scale), window=self.defect_center_button)
                self.mask_button_window=self.mycanvas.create_window(int(430*scale), panel_y0 + int(100*scale), window=self.mask_button)
            except Exception:
                pass

            # 统一中心对称排布，确保顺序与行高固定
            try:
                self._layout_buttons_centered()
            except Exception:
                pass

        # 重新绘制整个表盘
        self.drawbackground()
        if prev_running and hasattr(self, 'hand1') and hasattr(self, 'hand2'):
            try:
                self.mycanvas.coords(self.hand1, self.coordinateofA1())
                self.mycanvas.coords(self.hand2, self.coordinateofA2())
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

            # 运行时简化界面：完全按照父类dialgauge.py的隐藏逻辑
            # 只显示数字指示器和Stop按钮，隐藏所有其他控件
            self.mycanvas.coords(self.mystartwindow, -1000, -1000)
            self.mycanvas.coords(self.myresetwindow, -1200, -1200)

            # 隐藏所有控制组件，只保留Stop按钮和数字指示器
            self.mycanvas.coords(self.speed_label_window, -1200, -1200)
            self.mycanvas.coords(self.speed_scale_window, -1200, -1200)
            self.mycanvas.coords(self.preset_button_window, -1200, -1200)
            try:
                self.mycanvas.coords(self.horizontal_tilt_button_window, -1200, -1200)
            except Exception:
                pass
            self.mycanvas.coords(self.position_label_window, -1200, -1200)
            self.mycanvas.coords(self.position_info_window, -1200, -1200)
            self.mycanvas.coords(self.status_detail_window, -1200, -1200)
            self.mycanvas.coords(self.history_button_window, -1200, -1200)
            self.mycanvas.coords(self.mirror_button_window, -1200, -1200)
            self.mycanvas.coords(self.pointer_toggle_button_window, -1200, -1200)
            try:
                self.mycanvas.coords(self.mask_button_window, -1200, -1200)
            except Exception:
                pass
            # 隐藏新增按钮
            try:
                self.mycanvas.coords(self.defect_center_button_window, -1200, -1200)
                self.mycanvas.coords(self.mask_button_window, -1200, -1200)
            except Exception:
                pass

            # 确保数字指示器保持可见（不隐藏indicator）
            print("运行时界面简化：只显示数字指示器和Stop按钮")
            self.update()

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
        """恢复显示所有控制组件 - 调用统一排布，避免乱序"""
        try:
            self._layout_buttons_centered()
        except Exception:
            pass

    def _layout_buttons_centered(self):
        """与 dialgauge 保持一致的中心对称排布，固定按钮行序与左右信息区"""
        cx = int(self.centerx)
        py0 = int(self.canvaslength + 20*getattr(self, 'ui_scale', 1.0))
        step = int(120 * getattr(self, 'ui_scale', 1.0))

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

        place_row(row1, py0 + int(30*getattr(self, 'ui_scale', 1.0)))
        place_row(row2, py0 + int(80*getattr(self, 'ui_scale', 1.0)))
        place_row(row3, py0 + int(130*getattr(self, 'ui_scale', 1.0)))

        # 左侧速度，右侧状态
        try:
            dx = int(10*getattr(self, 'ui_scale', 1.0))
            # 与百分表保持一致：-2.6*step，y为20/85
            self.mycanvas.coords(self.speed_label_window, cx - int(2.6*step) + dx, py0 + int(20*getattr(self, 'ui_scale', 1.0)))
            self.mycanvas.coords(self.speed_scale_window, cx - int(2.6*step) + dx, py0 + int(85*getattr(self, 'ui_scale', 1.0)))
        except Exception:
            pass
        try:
            dx2 = int(10*getattr(self, 'ui_scale', 1.0))
            # 与百分表保持一致：+2.5*step，y为20/55/90
            self.mycanvas.coords(self.position_label_window, cx + int(2.5*step) - dx2, py0 + int(20*getattr(self, 'ui_scale', 1.0)))
            self.mycanvas.coords(self.position_info_window, cx + int(2.5*step) - dx2, py0 + int(55*getattr(self, 'ui_scale', 1.0)))
            self.mycanvas.coords(self.status_detail_window, cx + int(2.5*step) - dx2, py0 + int(90*getattr(self, 'ui_scale', 1.0)))
        except Exception:
            pass

        try:
            if getattr(self, 'preset_button_window', None) and getattr(self, 'horizontal_tilt_button_window', None):
                coords = self.mycanvas.coords(self.preset_button_window)
                if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                    px, py = coords[0], coords[1]
                    self.mycanvas.coords(self.horizontal_tilt_button_window, px, py + int(40*getattr(self, 'ui_scale', 1.0)))
        except Exception:
            pass

    def showcavnas(self):
        """显示画布和控件 - 重写父类方法以正确处理运行时隐藏逻辑"""
        self.pack()
        self.mycanvas.pack()

        # 根据运行状态决定控件的显示位置
        if hasattr(self, 'running') and self.running:
            # 运行时：应用隐藏逻辑，只显示Stop按钮和数字指示器
            self.mycanvas.coords(self.mystartwindow, -1000, -1000)
            self.mycanvas.coords(self.myresetwindow, -1200, -1200)

            # 隐藏所有控制组件，只保留Stop按钮和数字指示器
            self.mycanvas.coords(self.speed_label_window, -1200, -1200)
            self.mycanvas.coords(self.speed_scale_window, -1200, -1200)
            self.mycanvas.coords(self.preset_button_window, -1200, -1200)
            self.mycanvas.coords(self.position_label_window, -1200, -1200)
            self.mycanvas.coords(self.position_info_window, -1200, -1200)
            self.mycanvas.coords(self.status_detail_window, -1200, -1200)
            self.mycanvas.coords(self.history_button_window, -1200, -1200)
            self.mycanvas.coords(self.mirror_button_window, -1200, -1200)
            self.mycanvas.coords(self.pointer_toggle_button_window, -1200, -1200)
            # 隐藏新增按钮
            try:
                self.mycanvas.coords(self.defect_center_button_window, -1200, -1200)
                self.mycanvas.coords(self.mask_button_window, -1200, -1200)
                self.mycanvas.coords(self.horizontal_tilt_button_window, -1200, -1200)
            except Exception:
                pass

            print("showcavnas: 运行时界面简化 - 只显示数字指示器和Stop按钮")
        # 如果不在运行状态，控件位置已经在__init__中正确设置，无需额外处理

    def open_missing_ticks_manager(self):
        # 功能已移除
        try:
            tk.messagebox.showinfo("提示", "缺失刻线功能已移除")
        except Exception:
            pass

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
        if not hasattr(self, '_mask_items'):
            self._mask_items=[]
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

        self.mycanvas.tag_bind(item, '<Button-1>', _start)
        self.mycanvas.tag_bind(item, '<B1-Motion>', _drag)
        self.mycanvas.tag_bind(item, '<Button-3>', _rot_start)
        self.mycanvas.tag_bind(item, '<B3-Motion>', _rot_drag)

        try:
            self.mycanvas.tag_lower(item, self.hand1)
        except Exception:
            pass

    def toggle_center_offset(self):
        # 直接复用父类实现
        return super().toggle_center_offset()


if __name__ == "__main__":
    root=tk.Tk()
    #root.attributes('-fullscreen',True)
    root.title("dialgauge2")
    mygauge2=dialgauge2(root)
    mygauge2.drawbackground()
    mygauge2.showcavnas()
    mygauge2.update()
    mygauge2.mainloop()