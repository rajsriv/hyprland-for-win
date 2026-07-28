import sys
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPainterPath
from PyQt6.QtWidgets import QWidget, QApplication

class BorderWidget(QWidget):
    def __init__(self, screen, left_border=80, top_border=18, right_border=18, bottom_border=18, corner_radius=28, border_color="#fbc5cf"):
        super().__init__()
        self.target_screen = screen
        self.left_border = left_border
        self.top_border = top_border
        self.right_border = right_border
        self.bottom_border = bottom_border
        self.corner_radius = corner_radius
        self.border_color = QColor(border_color)
        
        # Set window flags to make it frameless, always-on-top, and transparent to inputs (click-through)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        # Enable translucent background
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        # Match target screen geometry
        self.update_geometry()
        
    def update_geometry(self):
        if self.target_screen:
            self.setGeometry(self.target_screen.availableGeometry())
            
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Clear the background first
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        
        # Draw the solid border color on the entire screen
        painter.setBrush(self.border_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())
        
        # Cut out the center area with rounded corners to make it transparent
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        
        # Define the inner rect that will be transparent, using asymmetrical borders
        w, h = self.width(), self.height()
        inner_rect = QRectF(
            self.left_border, 
            self.top_border, 
            w - self.left_border - self.right_border, 
            h - self.top_border - self.bottom_border
        )
        
        # Draw the rounded rect cutout
        painter.setBrush(Qt.GlobalColor.black)
        painter.drawRoundedRect(inner_rect, self.corner_radius, self.corner_radius)
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = BorderWidget()
    widget.show()
    sys.exit(app.exec())
