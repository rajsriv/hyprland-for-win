import sys
from PyQt6.QtCore import Qt, QTimer, QTime, QDate, QSize, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QIcon, QPainterPath, QPen
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, 
                             QSpacerItem, QSizePolicy, QApplication, QHBoxLayout)

class VerticalLabel(QWidget):
    """A widget to display text rotated vertically (-90 degrees)."""
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.text = text
        self.setFont(QFont("Segoe UI", 11, QFont.Weight.Medium))
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get parent theme state via top-level window
        is_light = getattr(self.window(), "is_light_theme", True)
        painter.setPen(QColor("#666666" if is_light else "#cccccc"))
        
        # Save state, translate to bottom-left, rotate -90, draw, restore
        painter.save()
        painter.translate(0, self.height())
        painter.rotate(-90)
        # Swap width/height for bounds since we rotated 90 degrees
        painter.drawText(0, 0, self.height(), self.width(), 
                         Qt.AlignmentFlag.AlignCenter, self.text)
        painter.restore()

class VectorButton(QPushButton):
    """A custom flat QPushButton that draws high-quality vector icons in paintEvent."""
    def __init__(self, icon_name, parent=None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.setFixedSize(32, 32)
        
    def paintEvent(self, event):
        # Draw background hover state using QSS
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        is_dark = not getattr(self.window(), "is_light_theme", True)
        
        # Select drawing color based on stylesheet constraints
        if self.objectName() == "btn_audio_active":
            color = QColor("#ffffff" if not is_dark else "#202124")
        elif self.objectName() == "btn_power":
            color = QColor("#d93025" if not is_dark else "#ff8bcb")
        else:
            color = QColor("#555555" if not is_dark else "#dddddd")
            
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        
        name = self.icon_name
        if name == "logo":
            # Stylized upward pointer triangle
            p = QPainterPath()
            p.moveTo(16, 9)
            p.lineTo(23, 21)
            p.lineTo(16, 18)
            p.lineTo(9, 21)
            p.closeSubpath()
            painter.drawPath(p)
            
        elif name == "moon":
            # Crescent Moon
            base = QPainterPath()
            base.addEllipse(QRectF(10, 10, 12, 12))
            sub = QPainterPath()
            sub.addEllipse(QRectF(13, 8, 12, 12))
            p = base.subtracted(sub)
            painter.drawPath(p)
            
        elif name == "sun":
            # Sun core
            p = QPainterPath()
            p.addEllipse(QRectF(12, 12, 8, 8))
            painter.drawPath(p)
            # Rays
            painter.setPen(QPen(color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(16, 7, 16, 9)
            painter.drawLine(16, 23, 16, 25)
            painter.drawLine(7, 16, 9, 16)
            painter.drawLine(23, 16, 25, 16)
            # Diagonal Rays
            painter.drawLine(10, 10, 12, 12)
            painter.drawLine(20, 20, 22, 22)
            painter.drawLine(22, 10, 20, 12)
            painter.drawLine(10, 20, 12, 22)
            
        elif name == "audio":
            # Speaker box
            p = QPainterPath()
            p.moveTo(8, 12)
            p.lineTo(11, 12)
            p.lineTo(15, 8)
            p.lineTo(15, 24)
            p.lineTo(11, 20)
            p.lineTo(8, 20)
            p.closeSubpath()
            painter.drawPath(p)
            # Sound waves
            painter.setPen(QPen(color, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRectF(11, 12, 8, 8), -45 * 16, 90 * 16)
            painter.drawArc(QRectF(8, 9, 14, 14), -45 * 16, 90 * 16)
            
        elif name == "dot":
            # Tiny dot
            p = QPainterPath()
            p.addEllipse(QRectF(14.5, 14.5, 3, 3))
            painter.drawPath(p)
            
        elif name == "settings":
            # Gear center ring
            p = QPainterPath()
            p.addEllipse(QRectF(11.5, 11.5, 9, 9))
            painter.drawPath(p)
            # Teeth
            painter.save()
            painter.translate(16, 16)
            for _ in range(8):
                painter.drawRect(QRectF(-1.5, -8, 3, 2.5))
                painter.rotate(45)
            painter.restore()
            # Clear cutout hole
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.drawEllipse(QRectF(14, 14, 4, 4))
            
        elif name == "calendar":
            # Calendar base border
            painter.setPen(QPen(color, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(9, 10, 14, 12), 1.5, 1.5)
            # Top header separator line
            painter.drawLine(9, 13, 23, 13)
            # Small binder hooks
            painter.drawLine(12, 8, 12, 10)
            painter.drawLine(20, 8, 20, 10)
            
        elif name == "bluetooth":
            # Bluetooth path
            painter.setPen(QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p = QPainterPath()
            p.moveTo(12, 12)
            p.lineTo(20, 20)
            p.lineTo(16, 24)
            p.lineTo(16, 8)
            p.lineTo(20, 12)
            p.lineTo(12, 20)
            painter.drawPath(p)
            
        elif name == "wifi":
            # Wifi signal waves
            painter.setPen(QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRectF(8, 9, 16, 16), 45 * 16, 90 * 16)
            painter.drawArc(QRectF(11, 12, 10, 10), 45 * 16, 90 * 16)
            # Bottom dot
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QRectF(14.5, 19, 3, 3))
            
        elif name == "power":
            # Power symbol open ring and line
            painter.setPen(QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(QRectF(10, 10, 12, 12), 125 * 16, 290 * 16)
            painter.drawLine(16, 7, 16, 14)

class SidebarWidget(QWidget):
    theme_changed = pyqtSignal(bool)
    def __init__(self):
        super().__init__()
        self.is_light_theme = True
        
        # Frameless, always on top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        self.init_ui()
        self.update_geometry()
        
        # Update clock timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        self.update_time()

    def init_ui(self):
        # The main layout is vertical
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Sidebar container/card
        self.container = QWidget(self)
        self.container.setObjectName("container")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(4, 12, 4, 12)
        self.container_layout.setSpacing(10)
        self.main_layout.addWidget(self.container)
        
        # --- TOP BUTTONS ---
        # Stylized compass/logo
        self.btn_logo = VectorButton("logo")
        self.btn_logo.setObjectName("btn_logo")
        
        # Light/Dark mode toggle
        self.btn_theme = VectorButton("moon")
        self.btn_theme.setObjectName("btn_theme")
        self.btn_theme.clicked.connect(self.toggle_theme)
        
        # Audio status (inside a blue active circle in the image)
        self.btn_audio = VectorButton("audio")
        self.btn_audio.setObjectName("btn_audio_active")
        self.btn_audio.clicked.connect(self.toggle_volume_mute)
        
        # Dot buttons
        self.btn_dot1 = VectorButton("dot")
        self.btn_dot1.setObjectName("btn_dot")
        self.btn_dot2 = VectorButton("dot")
        self.btn_dot2.setObjectName("btn_dot")
        
        self.container_layout.addWidget(self.btn_logo)
        self.container_layout.addWidget(self.btn_theme)
        self.container_layout.addWidget(self.btn_audio)
        self.container_layout.addWidget(self.btn_dot1)
        self.container_layout.addWidget(self.btn_dot2)
        
        # --- MIDDLE SECTION (Vertical text) ---
        self.container_layout.addStretch()
        
        self.vertical_lbl = VerticalLabel("Desktop", self)
        self.vertical_lbl.setFixedHeight(80)
        self.vertical_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.container_layout.addWidget(self.vertical_lbl)
        
        self.container_layout.addStretch()
        
        # --- BOTTOM SECTION (Settings, Clock, Status, Power) ---
        self.btn_settings = VectorButton("settings")
        self.btn_settings.setObjectName("btn_icon")
        self.btn_settings.clicked.connect(self.open_settings)
        
        self.btn_calendar = VectorButton("calendar")
        self.btn_calendar.setObjectName("btn_icon")
        self.btn_calendar.clicked.connect(self.open_calendar)
        
        # Clock label layout
        self.clock_layout = QVBoxLayout()
        self.clock_layout.setSpacing(2)
        self.lbl_hr = QLabel("12")
        self.lbl_min = QLabel("34")
        self.lbl_period = QLabel("PM")
        for lbl in (self.lbl_hr, self.lbl_min, self.lbl_period):
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setObjectName("clock_label")
        self.clock_layout.addWidget(self.lbl_hr)
        self.clock_layout.addWidget(self.lbl_min)
        self.clock_layout.addWidget(self.lbl_period)
        
        self.btn_bluetooth = VectorButton("bluetooth")
        self.btn_bluetooth.setObjectName("btn_icon")
        self.btn_bluetooth.clicked.connect(self.open_bluetooth)
        
        self.btn_wifi = VectorButton("wifi")
        self.btn_wifi.setObjectName("btn_icon")
        self.btn_wifi.clicked.connect(self.open_wifi)
        
        self.btn_power = VectorButton("power")
        self.btn_power.setObjectName("btn_power")
        self.btn_power.clicked.connect(self.close_app)
        
        self.container_layout.addWidget(self.btn_settings)
        self.container_layout.addWidget(self.btn_calendar)
        self.container_layout.addLayout(self.clock_layout)
        self.container_layout.addWidget(self.btn_bluetooth)
        self.container_layout.addWidget(self.btn_wifi)
        self.container_layout.addWidget(self.btn_power)
        
        self.apply_theme()
        
    def update_geometry(self, geom=None):
        screen = QApplication.primaryScreen()
        if screen:
            if geom is None:
                geom = screen.availableGeometry()
            # Wide left border is 60px, top and bottom are 10px.
            left_border = 60
            top_border = 10
            bottom_border = 10
            
            # Sidebar width should be narrower to fit inside 60px nicely
            sidebar_w = 40
            
            # Calculate height to sit within the top/bottom margins of the border
            margin_y = 10
            sidebar_h = geom.height() - top_border - bottom_border - (2 * margin_y)
            
            # Center the sidebar horizontally within the left border region
            x = geom.x() + (left_border - sidebar_w) // 2
            y = geom.y() + top_border + margin_y
            
            self.setGeometry(x, y, sidebar_w, sidebar_h)
            
    def update_time(self):
        time = QTime.currentTime()
        self.lbl_hr.setText(time.toString("hh"))
        self.lbl_min.setText(time.toString("mm"))
        self.lbl_period.setText(time.toString("AP"))
        
    def toggle_theme(self):
        self.is_light_theme = not self.is_light_theme
        self.btn_theme.icon_name = "sun" if not self.is_light_theme else "moon"
        self.btn_theme.update()
        self.apply_theme()
        self.vertical_lbl.update()
        self.theme_changed.emit(self.is_light_theme)
        
    def apply_theme(self):
        if self.is_light_theme:
            # Modern premium light styles
            self.setStyleSheet("""
                #container {
                    background-color: rgba(255, 255, 255, 0.9);
                    border: 1px solid rgba(255, 255, 255, 0.6);
                    border-radius: 20px;
                }
                QPushButton {
                    background: transparent;
                    border: none;
                    color: #444444;
                    font-size: 16px;
                    font-family: "Segoe UI", "Arial";
                    min-height: 32px;
                    min-width: 32px;
                    border-radius: 16px;
                }
                QPushButton:hover {
                    background-color: rgba(0, 0, 0, 0.05);
                }
                #btn_logo {
                    font-size: 18px;
                    color: #7d5260;
                }
                #btn_audio_active {
                    background-color: #1a73e8;
                    color: white;
                    font-size: 13px;
                }
                #btn_audio_active:hover {
                    background-color: #1557b0;
                }
                #btn_dot {
                    font-size: 14px;
                    color: #888888;
                }
                #clock_label {
                    color: #333333;
                    font-family: "Segoe UI Semibold", "Arial";
                    font-size: 11px;
                }
                #btn_power {
                    color: #d93025;
                }
                #btn_power:hover {
                    background-color: rgba(217, 48, 37, 0.1);
                }
            """)
        else:
            # Modern premium dark styles
            self.setStyleSheet("""
                #container {
                    background-color: rgba(30, 30, 30, 0.9);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 20px;
                }
                QPushButton {
                    background: transparent;
                    border: none;
                    color: #dddddd;
                    font-size: 16px;
                    font-family: "Segoe UI", "Arial";
                    min-height: 32px;
                    min-width: 32px;
                    border-radius: 16px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 255, 255, 0.08);
                }
                #btn_logo {
                    font-size: 18px;
                    color: #ffb4a2;
                }
                #btn_audio_active {
                    background-color: #8ab4f8;
                    color: #202124;
                    font-size: 13px;
                }
                #btn_audio_active:hover {
                    background-color: #aecbfa;
                }
                #btn_dot {
                    font-size: 14px;
                    color: #aaaaaa;
                }
                #clock_label {
                    color: #eeeeee;
                    font-family: "Segoe UI Semibold", "Arial";
                    font-size: 11px;
                }
                #btn_power {
                    color: #ff8bcb;
                }
                #btn_power:hover {
                    background-color: rgba(255, 139, 203, 0.15);
                }
            """)

    def close_app(self):
        QApplication.quit()

    def toggle_volume_mute(self):
        import ctypes
        # Send VK_VOLUME_MUTE key event (0xAD)
        ctypes.windll.user32.keybd_event(0xAD, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0xAD, 0, 2, 0)

    def open_settings(self):
        import os
        os.system("start ms-settings:")

    def open_calendar(self):
        import os
        os.system("start ms-settings:dateandtime")

    def open_bluetooth(self):
        import os
        os.system("start ms-settings:bluetooth")

    def open_wifi(self):
        import os
        os.system("start ms-settings:network")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    sidebar = SidebarWidget()
    sidebar.show()
    sys.exit(app.exec())
