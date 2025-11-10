import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

import tkinter as tk

from dialgauge import dialgauge


class dialgauge3(dialgauge):
    def __init__(self, master=None):
        super().__init__(master)

        # 数字表：不显示指针，仅显示数字
        self.pointers_visible = False

        # 数字显示精度（2或3位小数可切换）；小数点前第二位按需显示
        self.digital_precision = 2
        self.integer_min_digits = 1
        # 数码段关闭态与底板统一的灰色（参考“暗的0”）
        self._digital_off_color = '#B0B5BA'

        # 预设位置（单位：mm）- 数字表沿用父类运行/暂停逻辑
        # 可按需修改此列表以改变运行顺序/停靠点
        self.preset_positions = [
            0.00,0.020,0.040,0.060,0.080,0.100,0.120,0.140,0.160,0.180,0.200,
           0.180,0.160,0.140,0.120,0.100,0.080,0.060,0.040,0.020,0.000
        ]

        # 放大但隐藏原文字指示器（作为占位，运行/停止逻辑沿用父类）
        try:
            scale = getattr(self, 'ui_scale', 1.0)
            self.indicator.config(
                font=("Arial", max(20, int(64 * scale)), "bold"),
                width=14,
                bg="#FFFFFF",
                fg="#000000",
            )
        except Exception:
            pass

        # 指针开关在数字表中无意义，禁用并移出画布
        try:
            self.pointer_toggle_button.config(text="🔢 Digital Only", state=tk.DISABLED)
            if hasattr(self, 'pointer_toggle_button_window'):
                try:
                    self.mycanvas.coords(self.pointer_toggle_button_window, -1200, -1200)
                except Exception:
                    pass
        except Exception:
            pass

        # 去除可能存在的指针图元，并避免重复的速度/状态窗口
        try:
            self.mycanvas.delete('needle')
        except Exception:
            pass
        # 数字表保留速度滑块与状态区，因此不删除这两个窗口
        # 初始按数字表的布局进行一次排布
        try:
            self._layout_digital_controls()
        except Exception:
            pass

        # 初始化 8 段（7段+小数点）数字显示
        self._seg_digits = []  # 每位的段元素id集合
        self._seg_meta = {}    # 尺寸与位置缓存
        self._init_segment_display()

        # 完全隐藏原文字指示器（避免覆盖数码段）
        try:
            self.indicator.configure(text="")
            if hasattr(self, 'indicatorwindow') and self.indicatorwindow:
                self.mycanvas.coords(self.indicatorwindow, -1200, -1200)
        except Exception:
            pass

    # 覆盖：数字表不创建任何指针
    def ensure_pointers_created(self):
        return

    # 简化背景绘制：不绘制刻度与表盘，仅绘制数字底板与8段数码
    def drawbackground(self):
        try:
            # 不清空控件窗口，避免重建；仅移动并居中数字显示
            cx, cy = int(self.centerx), int(self.centery)
            # 原indicator移出画布，完全不显示
            if hasattr(self, 'indicatorwindow') and self.indicatorwindow:
                try:
                    self.mycanvas.coords(self.indicatorwindow, -1200, -1200)
                except Exception:
                    self.indicatorwindow = self.mycanvas.create_window(-1200, -1200, window=self.indicator)
            else:
                self.indicatorwindow = self.mycanvas.create_window(-1200, -1200, window=self.indicator)

            # 绘制一个柔和的发光底板以衬托数字（整体按0.75缩放）
            w = int(self.canvaslength * 0.675)
            h = int(self.canvaslength * 0.21)
            x0, y0 = cx - w // 2, cy - h // 2
            x1, y1 = cx + w // 2, cy + h // 2
            # 先清理旧的底板
            try:
                if hasattr(self, '_digital_plate') and self._digital_plate:
                    self.mycanvas.delete(self._digital_plate)
            except Exception:
                pass
            bbox = self._apply_tilt_to_bbox((x0, y0, x1, y1))
            self._digital_plate = self.mycanvas.create_rectangle(
                *bbox,
                outline="#70757A",
                width=2,
                fill=self._digital_off_color,
                tags=('digital',)
            )
            # 重新布局并重建数码段
            self._init_segment_display()

        except Exception:
            pass

    # 覆盖镜像：数字表支持镜像（水平翻转数码段与底板）
    def toggle_mirror(self):
        prev_running = bool(getattr(self, 'running', False))
        self.is_mirrored = not getattr(self, 'is_mirrored', False)
        # 更新按钮外观（沿用父类风格）
        try:
            if hasattr(self, 'mirror_button'):
                if self.is_mirrored:
                    self.mirror_button.config(text="🔄 Mirror ON", bg="#FFD700", activebackground="#E6C200")
                else:
                    self.mirror_button.config(text="🔄 Mirror OFF", bg="#F0E68C", activebackground="#E6DA7A")
        except Exception:
            pass

        # 对当前数字图元进行水平镜像（以中心为原点）
        try:
            cx, cy = float(self.centerx), float(self.centery)
            self.mycanvas.scale('digital', cx, cy, -1, 1)
        except Exception:
            pass

        # 运行状态与控件布局保持父类逻辑
        if prev_running:
            # 运行时界面不变，仅图形镜像
            pass
        else:
            try:
                self._layout_digital_controls()
            except Exception:
                pass

    # 运行/停止时保持数字表布局稳定，并在运行时只保留Stop与数字
    def start(self):
        was_running = getattr(self, 'running', False)
        super().start()
        # 运行时仅保留Stop与数字，隐藏其他
        try:
            self._hide_controls_for_run()
        except Exception:
            pass

    def restore_all_controls(self):
        super().restore_all_controls()
        try:
            self._layout_digital_controls()
        except Exception:
            pass
        try:
            self._update_segment_display()
        except Exception:
            pass

    def toggle_center_offset(self):
        # 数字表不支持中心偏移
        return

    # 数字表专用布局：保留三行按钮；隐藏“指针开关”“镜像”“中心偏移”“Mask”；速度滑块在左，灰色状态在右
    def _layout_digital_controls(self):
        scale = getattr(self, 'ui_scale', 1.0)
        cx = int(getattr(self, 'centerx', 400))
        step = int(120 * scale)
        py0 = int(self.canvaslength + 20*scale)

        # 第一行（Start/Stop/Reset）和第二行（History/Mirror/Pointer）位置由父类创建，这里仅调整隐藏Pointer
        try:
            if hasattr(self, 'pointer_toggle_button_window') and self.pointer_toggle_button_window:
                self.mycanvas.coords(self.pointer_toggle_button_window, -1200, -1200)
        except Exception:
            pass

        # 第三行：去掉 Center Offset 与 Mask，仅保留 Presets（靠右）
        try:
            if hasattr(self, 'defect_center_button_window') and self.defect_center_button_window:
                self.mycanvas.coords(self.defect_center_button_window, -1200, -1200)
        except Exception:
            pass
        try:
            if hasattr(self, 'mask_button_window') and self.mask_button_window:
                self.mycanvas.coords(self.mask_button_window, -1200, -1200)
            # 若已存在遮罩图形，清空
            if hasattr(self, '_mask_items') and self._mask_items:
                for it in list(self._mask_items):
                    try:
                        self.mycanvas.delete(it)
                    except Exception:
                        pass
                self._mask_items = []
        except Exception:
            pass
        try:
            if hasattr(self, 'preset_button_window') and self.preset_button_window:
                # 与第二行（History/Mirror）同一行，放在右侧占位（原Pointer位置）
                self.mycanvas.coords(self.preset_button_window, cx + step, py0 + int(80*scale))
        except Exception:
            pass
        try:
            if hasattr(self, 'horizontal_tilt_button_window') and self.horizontal_tilt_button_window and hasattr(self, 'preset_button_window'):
                coords = self.mycanvas.coords(self.preset_button_window)
                if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                    px, py = coords[0], coords[1]
                    self.mycanvas.coords(self.horizontal_tilt_button_window, px, py + int(40*scale))
        except Exception:
            pass

        # 精度切换按钮（2位/3位）— 放到第三行靠左，避免重叠
        try:
            if not hasattr(self, 'precision_button'):
                self.precision_button = tk.Button(self, text=f"Dec: {self.digital_precision}",
                                                  command=self._toggle_precision,
                                                  font=("Arial", max(8,int(10*getattr(self,'ui_scale',1.0)))),
                                                  bg="#2f4f4f", fg="#ffffff", width=8)
            y3 = py0 + int(130*getattr(self,'ui_scale',1.0))
            if not hasattr(self, 'precision_button_window') or not self.precision_button_window:
                self.precision_button_window = self.mycanvas.create_window(cx - step, y3, window=self.precision_button)
            else:
                self.mycanvas.coords(self.precision_button_window, cx - step, y3)
        except Exception:
            pass

        # 左右辅助区：速度在左，状态在右
        try:
            if hasattr(self, 'speed_label_window'):
                self.mycanvas.coords(self.speed_label_window, cx - 2.6*step + int(10*getattr(self, 'ui_scale', 1.0)), py0 + int(20*getattr(self, 'ui_scale', 1.0)))
            if hasattr(self, 'speed_scale_window'):
                self.mycanvas.coords(self.speed_scale_window, cx - 2.6*step + int(15*getattr(self, 'ui_scale', 1.0)), py0 + int(85*getattr(self, 'ui_scale', 1.0)))
        except Exception:
            pass
        try:
            if hasattr(self, 'position_label_window'):
                self.mycanvas.coords(self.position_label_window, cx + 2.5*step - int(10*getattr(self, 'ui_scale', 1.0)), py0 + int(20*getattr(self, 'ui_scale', 1.0)))
            if hasattr(self, 'position_info_window'):
                self.mycanvas.coords(self.position_info_window, cx + 2.5*step - int(10*getattr(self, 'ui_scale', 1.0)), py0 + int(55*getattr(self, 'ui_scale', 1.0)))
            if hasattr(self, 'status_detail_window'):
                self.mycanvas.coords(self.status_detail_window, cx + 2.5*step - int(10*getattr(self, 'ui_scale', 1.0)), py0 + int(90*getattr(self, 'ui_scale', 1.0)))
        except Exception:
            pass

    def _hide_controls_for_run(self):
        """运行时仅保留Stop与数字，其余移动出画布。"""
        py0 = int(self.canvaslength + 20*getattr(self, 'ui_scale', 1.0))
        # 允许Stop继续显示（父类已放在中行中位）
        # 隐藏速度、状态、Mask、Presets、History、Mirror、Start、Reset、Pointer、Center Offset
        names = [
            'speed_label_window','speed_scale_window',
            'position_label_window','position_info_window','status_detail_window',
            'history_button_window','mirror_button_window','pointer_toggle_button_window',
            'mystartwindow','myresetwindow','defect_center_button_window','mask_button_window','preset_button_window',
            'horizontal_tilt_button_window',
            'precision_button_window'
        ]
        for n in names:
            try:
                w = getattr(self, n, None)
                if w:
                    self.mycanvas.coords(w, -1200, -1200)
            except Exception:
                pass

    def _toggle_precision(self):
        self.digital_precision = 2 if self.digital_precision == 3 else 3
        try:
            self.precision_button.config(text=f"Dec: {self.digital_precision}")
        except Exception:
            pass
        # 精度改变会影响位数布局，重建段位
        self._init_segment_display()

    # ============== 8段数码显示 ==============
    def _init_segment_display(self):
        """根据当前画布尺寸在中心重建所有数码段。"""
        try:
            # 清理旧段
            if hasattr(self, '_seg_digits') and self._seg_digits:
                for d in self._seg_digits:
                    for item in d.values():
                        try:
                            self.mycanvas.delete(item)
                        except Exception:
                            pass
            self._seg_digits = []
            # 清理单位文字
            try:
                if hasattr(self, '_unit_text') and self._unit_text:
                    self.mycanvas.delete(self._unit_text)
                    self._unit_text = None
            except Exception:
                pass

            cx, cy = int(self.centerx), int(self.centery)
            # 与底板同步按0.75缩放（0.9→0.675, 0.28→0.21）
            plate_w = int(self.canvaslength * 0.5)
            plate_h = int(self.canvaslength * 0.21)
            # 将小数点锚定在固定槽位，保证2位/3位小数切换时位置不偏移
            dp_anchor = 1  # 小数点左侧整数位所在的槽索引
            # 统一按3位小数的布局来计算槽位，使2位小数时数字大小与3位一致
            dpn_fmt = int(self.digital_precision)
            dpn_layout = max(dpn_fmt, 3)
            max_digits = max(4, dp_anchor + dpn_layout + 1)  # dp=2/3 -> 5
            seg_th = max(4, int(plate_h * 0.08))
            digit_w = int(plate_w / (max_digits + 1))
            digit_h = int(plate_h * 0.8)
            # 数字间距固定为约2.5mm（按96DPI≈3.78px/mm换算）
            gap = max(2, int(round(4.5* 3.78)))
            start_x = cx - (max_digits * digit_w + (max_digits - 1) * gap) // 2
            top_y = cy - digit_h // 2

            self._seg_meta = {
                'max_digits': max_digits,
                'seg_th': seg_th,
                'digit_w': digit_w,
                'digit_h': digit_h,
                'gap': gap,
                'origin_x': start_x,
                'origin_y': top_y,
                'color_on': '#0F0F10',
                'color_off': self._digital_off_color,
                'dp_anchor': dp_anchor,
            }

            for i in range(max_digits):
                x = start_x + i * (digit_w + gap)
                self._seg_digits.append(self._create_digit_segments(x, top_y, digit_w, digit_h, seg_th))

            # 单位“mm”
            try:
                unit_font = ("Arial", max(10, int(12*getattr(self,'ui_scale',1.0))), "bold")
                unit_x = start_x + max_digits * (digit_w + gap) + int(gap*1.5)
                unit_y = cy
                unit_tx, unit_ty = self._apply_tilt_to_point(unit_x, unit_y)
                self._unit_text = self.mycanvas.create_text(unit_tx, unit_ty, text="mm", fill="#0F0F10", anchor='w', font=unit_font, tags=('digital',))
            except Exception:
                pass

            # 若处于镜像状态，对数字图元整体进行镜像
            try:
                if getattr(self, 'is_mirrored', False):
                    self.mycanvas.scale('digital', float(self.centerx), float(self.centery), -1, 1)
            except Exception:
                pass

            self._update_segment_display()
        except Exception:
            pass

    def _create_digit_segments(self, x, y, w, h, t):
        """创建单个数字位的7段(带斜边)+小数点，返回字典。"""
        off = self._seg_meta.get('color_off', '#B0B5BA')
        segs = {}

        bev = max(2, int(t * 0.55))  # 斜边长度

        # 辅助：创建带斜边的水平段
        def _hseg(x0, y0, length, thick):
            lx = length
            ly = thick
            pts = [
                x0 + bev,         y0,
                x0 + lx - bev,    y0,
                x0 + lx,          y0 + ly // 2,
                x0 + lx - bev,    y0 + ly,
                x0 + bev,         y0 + ly,
                x0,               y0 + ly // 2,
            ]
            pts_t = self._apply_tilt_to_coords(pts)
            return self.mycanvas.create_polygon(pts_t, fill=off, outline='', tags=('digital',))

        # 辅助：创建带斜边的垂直段
        def _vseg(x0, y0, thick, length):
            lx = length
            ly = thick
            pts = [
                x0,               y0 + bev,
                x0 + ly // 2,     y0,
                x0 + ly,          y0 + bev,
                x0 + ly,          y0 + lx - bev,
                x0 + ly // 2,     y0 + lx,
                x0,               y0 + lx - bev,
            ]
            pts_t = self._apply_tilt_to_coords(pts)
            return self.mycanvas.create_polygon(pts_t, fill=off, outline='', tags=('digital',))

        # 水平段 a, g, d（位于上、中、下）
        segs['a'] = _hseg(x + t, y, w - 2 * t, t)
        segs['g'] = _hseg(x + t, y + (h // 2 - t // 2), w - 2 * t, t)
        segs['d'] = _hseg(x + t, y + h - t, w - 2 * t, t)

        # 左侧垂直 f (上半) 与 e (下半)
        segs['f'] = _vseg(x, y + t, t, (h // 2 - t))
        segs['e'] = _vseg(x, y + (h // 2 + t // 2), t, (h // 2 - t))

        # 右侧垂直 b (上半) 与 c (下半)
        segs['b'] = _vseg(x + w - t, y + t, t, (h // 2 - t))
        segs['c'] = _vseg(x + w - t, y + (h // 2 + t // 2), t, (h // 2 - t))

        # 小数点
        r = max(2, t // 2)
        dp_bbox = (x + w + r // 2, y + h - r, x + w + r // 2 + r, y + h)
        dp_bbox_t = self._apply_tilt_to_bbox(dp_bbox)
        segs['dp'] = self.mycanvas.create_oval(*dp_bbox_t, fill=off, outline='', tags=('digital',))
        return segs

    def _update_segment_display(self):
        """根据当前值刷新8段数码显示。"""
        if not self._seg_digits:
            return
        try:
            # 使用父类的平滑数值 _display_value（若不存在则使用 lengthofmeas）
            val = float(getattr(self, '_display_value', getattr(self, 'lengthofmeas', 0.0)))
            dp = int(self.digital_precision)
            # 固定最少整数位显示（前置零），并带小数点；不做额外改写
            width = int(self.integer_min_digits + 1 + max(0, dp))
            s = f"{val:0{width}.{dp}f}"
            # 仅保留数字与小数点
            digits = [ch for ch in s if ch.isdigit()]
            dp_index = s.find('.')  # 小数点在字符串中的索引
            # 小数点属于点前一位，统计整数位数
            int_cnt = len([ch for ch in s[:dp_index] if ch.isdigit()]) if dp_index != -1 else len(digits)

            # 以小数点锚位对齐：第一个整数位的槽 = 锚位 - (整数位数-1)
            max_digits = self._seg_meta['max_digits']
            anchor = int(self._seg_meta.get('dp_anchor', 1))
            start = anchor - (max(1, int_cnt) - 1)
            # 先全部熄灭
            for i in range(max_digits):
                for key in ('a','b','c','d','e','f','g','dp'):
                    self.mycanvas.itemconfig(self._seg_digits[i][key], fill=self._seg_meta['color_off'])

            mapping = {
                '0': ('a','b','c','d','e','f'),
                '1': ('b','c'),
                '2': ('a','b','d','e','g'),
                '3': ('a','b','c','d','g'),
                '4': ('f','g','b','c'),
                '5': ('a','f','g','c','d'),
                '6': ('a','f','e','d','c','g'),
                '7': ('a','b','c'),
                '8': ('a','b','c','d','e','f','g'),
                '9': ('a','b','c','d','f','g'),
            }

            for idx, ch in enumerate(digits):
                i = start + idx
                if i < 0 or i >= max_digits:
                    continue
                for seg in mapping.get(ch, ()):  # 点亮对应段
                    self.mycanvas.itemconfig(self._seg_digits[i][seg], fill=self._seg_meta['color_on'])
            # 小数点
            if dp_index != -1:
                i = anchor
                if 0 <= i < max_digits:
                    self.mycanvas.itemconfig(self._seg_digits[i]['dp'], fill=self._seg_meta['color_on'])
        except Exception:
            pass

    def reset(self):
        # 保留父类重置逻辑
        super().reset()
        # 同步数码段显示到复位值
        try:
            self._display_value = float(getattr(self, 'lengthofmeas', 0.0))
        except Exception:
            self._display_value = 0.0
        try:
            self._update_segment_display()
        except Exception:
            pass

    def update(self):
        # 先执行父类的状态更新/调度
        super().update()
        # 然后刷新8段显示
        try:
            self._update_segment_display()
        except Exception:
            pass


if __name__ == "__main__":
    root = tk.Tk()
    root.title("dialgauge3 - Digital")
    g = dialgauge3(root)
    g.drawbackground()
    g.showcavnas()
    g.update()
    root.mainloop()


