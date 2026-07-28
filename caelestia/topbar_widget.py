import sys
import ctypes
from ctypes import wintypes
from PyQt6.QtCore import Qt, QTimer, QTime, QRectF, QPropertyAnimation
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QPainterPath
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QLabel, QPushButton, 
                             QSizePolicy, QApplication)

# Windows structures for CPU and RAM monitoring
class FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD)
    ]

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64)
    ]

# CPU usage global variables
last_idle_time = 0
last_kernel_time = 0
last_user_time = 0

def get_cpu_usage():
    global last_idle_time, last_kernel_time, last_user_time
    idle = FILETIME()
    kernel = FILETIME()
    user = FILETIME()
    
    ctypes.windll.kernel32.GetSystemTimes(
        ctypes.byref(idle),
        ctypes.byref(kernel),
        ctypes.byref(user)
    )
    
    def filetime_to_int(ft):
        return (ft.dwHighDateTime << 32) + ft.dwLowDateTime
        
    curr_idle = filetime_to_int(idle)
    curr_kernel = filetime_to_int(kernel)
    curr_user = filetime_to_int(user)
    
    idle_diff = curr_idle - last_idle_time
    kernel_diff = curr_kernel - last_kernel_time
    user_diff = curr_user - last_user_time
    
    last_idle_time = curr_idle
    last_kernel_time = curr_kernel
    last_user_time = curr_user
    
    total = kernel_diff + user_diff
    if total == 0:
        return 0
    usage = int(100 * (total - idle_diff) / total)
    return max(0, min(100, usage))

def get_ram_usage():
    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    return stat.dwMemoryLoad

class TopbarVectorButton(QPushButton):
    """Draws custom vector symbols in the Top Bar."""
    def __init__(self, icon_name, parent=None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.setFixedSize(24, 24)
        
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        is_dark = not getattr(self.window(), "is_light_theme", True)
        color = QColor("#333333" if not is_dark else "#dddddd")
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        
        name = self.icon_name
        if name == "play":
            p = QPainterPath()
            p.moveTo(8, 6)
            p.lineTo(18, 12)
            p.lineTo(8, 18)
            p.closeSubpath()
            painter.drawPath(p)
        elif name == "pause":
            painter.drawRect(QRectF(7, 6, 3, 12))
            painter.drawRect(QRectF(14, 6, 3, 12))
        elif name == "skip":
            p = QPainterPath()
            p.moveTo(6, 6)
            p.lineTo(14, 12)
            p.lineTo(6, 18)
            p.closeSubpath()
            painter.drawPath(p)
            painter.drawRect(QRectF(15, 6, 2, 12))
            
class WorkspaceDotWidget(QWidget):
    """Shows dots representing workspaces."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(80, 24)
        self.active_idx = 0
        
    def mousePressEvent(self, event):
        # Allow clicking dots to change index
        clicked_x = event.position().x()
        idx = int(clicked_x // 16)
        if 0 <= idx < 5:
            self.active_idx = idx
            self.update()
            
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        is_dark = not getattr(self.window(), "is_light_theme", True)
        
        for i in range(5):
            x = 8 + i * 16
            y = 12
            radius = 4 if i == self.active_idx else 2.5
            color = QColor("#1a73e8" if i == self.active_idx else ("#bbbbbb" if not is_dark else "#555555"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QRectF(x - radius, y - radius, 2 * radius, 2 * radius))

class TopbarWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.is_light_theme = True
        self.is_visible_state = False
        self.anim = None
        
        # Frameless window stays on top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        self.init_ui()
        self.update_geometry()
        
        # Start system monitor timer
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.update_system_stats)
        self.monitor_timer.start(1500)
        
        # Start mouse tracking/hover timer
        self.mouse_timer = QTimer(self)
        self.mouse_timer.timeout.connect(self.check_mouse_hover)
        self.mouse_timer.start(100)
        
        # Delay timer before hiding top bar
        self.hide_delay_timer = QTimer(self)
        self.hide_delay_timer.setSingleShot(True)
        self.hide_delay_timer.timeout.connect(self.slide_up)
        
        # Warm up CPU stats
        get_cpu_usage()
        self.update_system_stats()
        
        # Hide initially
        self.hide()

    def init_ui(self):
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Top Bar Container
        self.container = QWidget(self)
        self.container.setObjectName("container")
        self.container_layout = QHBoxLayout(self.container)
        self.container_layout.setContentsMargins(15, 0, 15, 0)
        self.container_layout.setSpacing(15)
        self.main_layout.addWidget(self.container)
        
        # --- LEFT SECTION: WORKSPACE DOTS ---
        self.workspaces = WorkspaceDotWidget(self)
        self.container_layout.addWidget(self.workspaces)
        
        # Separator line
        self.sep1 = QLabel("|")
        self.sep1.setObjectName("separator")
        self.container_layout.addWidget(self.sep1)
        
        # --- MIDDLE SECTION: MEDIA PLAYER ---
        self.lbl_media = QLabel("Now Playing: Caelestia Ambient Stream")
        self.lbl_media.setObjectName("lbl_media")
        self.lbl_media.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
        
        self.btn_play = TopbarVectorButton("pause", self)
        self.btn_play.clicked.connect(self.toggle_play)
        self.is_playing = True
        
        self.btn_skip = TopbarVectorButton("skip", self)
        
        self.container_layout.addWidget(self.lbl_media)
        self.container_layout.addWidget(self.btn_play)
        self.container_layout.addWidget(self.btn_skip)
        
        # Separator line
        self.sep2 = QLabel("|")
        self.sep2.setObjectName("separator")
        self.container_layout.addWidget(self.sep2)
        
        # --- RIGHT SECTION: SYSTEM STATS ---
        self.lbl_cpu = QLabel("CPU: 0%")
        self.lbl_cpu.setObjectName("lbl_stat")
        self.lbl_cpu.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        
        self.lbl_ram = QLabel("RAM: 0%")
        self.lbl_ram.setObjectName("lbl_stat")
        self.lbl_ram.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        
        self.container_layout.addWidget(self.lbl_cpu)
        self.container_layout.addWidget(self.lbl_ram)
        
        self.apply_theme()

    def update_geometry(self, geom=None):
        screen = QApplication.primaryScreen()
        if screen:
            screen_geom = screen.geometry()
            topbar_w = 640
            topbar_h = 36
            x = screen_geom.x() + (screen_geom.width() - topbar_w) // 2
            # Offscreen initially depending on visibility state
            if self.is_visible_state:
                self.setGeometry(x, screen_geom.y() + 4, topbar_w, topbar_h)
            else:
                self.setGeometry(x, screen_geom.y() - topbar_h, topbar_w, topbar_h)

    def check_mouse_hover(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return
            
        geom = screen.geometry()
        cursor_pos = self.cursor().pos()
        
        # Detection zone: 300px wide, 8px high at the absolute top center
        trigger_w = 300
        trigger_h = 8
        trigger_x_start = geom.x() + (geom.width() - trigger_w) // 2
        trigger_x_end = trigger_x_start + trigger_w
        trigger_y_start = geom.y()
        trigger_y_end = geom.y() + trigger_h
        
        in_trigger = (trigger_x_start <= cursor_pos.x() <= trigger_x_end and 
                      trigger_y_start <= cursor_pos.y() <= trigger_y_end)
                      
        in_topbar = False
        if self.isVisible():
            # Check if mouse is within the top bar geometry bounds
            in_topbar = self.geometry().contains(cursor_pos)
            
        if in_trigger or in_topbar:
            self.hide_delay_timer.stop()
            if not self.is_visible_state:
                self.slide_down()
        else:
            if self.is_visible_state and not self.hide_delay_timer.isActive():
                # Start delay countdown to slide up (800ms)
                self.hide_delay_timer.start(800)

    def slide_down(self):
        if self.anim and self.anim.state() == QPropertyAnimation.State.Running:
            self.anim.stop()
            
        self.is_visible_state = True
        self.show()
        self.raise_()
        
        screen = QApplication.primaryScreen()
        if screen:
            screen_geom = screen.geometry()
            topbar_w = 640
            topbar_h = 36
            x = screen_geom.x() + (screen_geom.width() - topbar_w) // 2
            
            start_rect = self.geometry()
            end_rect = QRectF(x, screen_geom.y() + 4, topbar_w, topbar_h).toRect()
            
            self.anim = QPropertyAnimation(self, b"geometry")
            self.anim.setDuration(220)
            self.anim.setStartValue(start_rect)
            self.anim.setEndValue(end_rect)
            self.anim.start()

    def slide_up(self):
        if self.anim and self.anim.state() == QPropertyAnimation.State.Running:
            self.anim.stop()
            
        self.is_visible_state = False
        
        screen = QApplication.primaryScreen()
        if screen:
            screen_geom = screen.geometry()
            topbar_w = 640
            topbar_h = 36
            x = screen_geom.x() + (screen_geom.width() - topbar_w) // 2
            
            start_rect = self.geometry()
            end_rect = QRectF(x, screen_geom.y() - topbar_h, topbar_w, topbar_h).toRect()
            
            self.anim = QPropertyAnimation(self, b"geometry")
            self.anim.setDuration(220)
            self.anim.setStartValue(start_rect)
            self.anim.setEndValue(end_rect)
            self.anim.finished.connect(self.hide_on_finished)
            self.anim.start()
            
    def hide_on_finished(self):
        if not self.is_visible_state:
            self.hide()

    def toggle_play(self):
        self.is_playing = not self.is_playing
        self.btn_play.icon_name = "pause" if self.is_playing else "play"
        self.btn_play.update()
        if self.is_playing:
            self.lbl_media.setText("Now Playing: Caelestia Ambient Stream")
        else:
            self.lbl_media.setText("Music Paused")

    def update_system_stats(self):
        cpu = get_cpu_usage()
        ram = get_ram_usage()
        self.lbl_cpu.setText(f"CPU: {cpu}%")
        self.lbl_ram.setText(f"RAM: {ram}%")

    def toggle_theme(self, is_light):
        self.is_light_theme = is_light
        self.apply_theme()
        self.workspaces.update()
        self.btn_play.update()
        self.btn_skip.update()

    def apply_theme(self):
        if self.is_light_theme:
            self.setStyleSheet("""
                #container {
                    background-color: rgba(255, 255, 255, 0.9);
                    border: 1px solid rgba(255, 255, 255, 0.6);
                    border-radius: 18px;
                }
                QLabel {
                    color: #333333;
                }
                #separator {
                    color: #cccccc;
                }
                #lbl_media {
                    color: #555555;
                }
                #lbl_stat {
                    color: #1a73e8;
                }
                QPushButton {
                    background: transparent;
                    border: none;
                    border-radius: 12px;
                }
                QPushButton:hover {
                    background-color: rgba(0, 0, 0, 0.05);
                }
            """)
        else:
            self.setStyleSheet("""
                #container {
                    background-color: rgba(30, 30, 30, 0.9);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 18px;
                }
                QLabel {
                    color: #eeeeee;
                }
                #separator {
                    color: #444444;
                }
                #lbl_media {
                    color: #bbbbbb;
                }
                #lbl_stat {
                    color: #8ab4f8;
                }
                QPushButton {
                    background: transparent;
                    border: none;
                    border-radius: 12px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.08);
                }
            """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    bar = TopbarWidget()
    bar.show()
    sys.exit(app.exec())
