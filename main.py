import sys
import ctypes
from ctypes import wintypes
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QTimer, QRectF, QAbstractNativeEventFilter
from border_widget import BorderWidget
from topbar_widget import TopbarWidget

# Define RECT structure for Windows API
class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG)
    ]

# Define MONITORINFO structure to retrieve screen boundaries
class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD)
    ]

# Windows API declarations
EnumWindows = ctypes.windll.user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
IsWindowVisible = ctypes.windll.user32.IsWindowVisible
IsZoomed = ctypes.windll.user32.IsZoomed
ShowWindow = ctypes.windll.user32.ShowWindow
MoveWindow = ctypes.windll.user32.MoveWindow

# Setup function signatures to prevent crashes/errors
ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
ShowWindow.restype = wintypes.BOOL

MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]
MoveWindow.restype = wintypes.BOOL

IsZoomed.argtypes = [wintypes.HWND]
IsZoomed.restype = wintypes.BOOL

IsWindowVisible.argtypes = [wintypes.HWND]
IsWindowVisible.restype = wintypes.BOOL

class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        
    def nativeEventFilter(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312:  # WM_HOTKEY
                if msg.wParam == 99:
                    self.callback()
                    return True, 0
        return False, 0

def get_work_area():
    """Retrieve the current desktop work area rect on Windows."""
    SPI_GETWORKAREA = 0x0030
    rect = RECT()
    ctypes.windll.user32.SystemParametersInfoW(
        SPI_GETWORKAREA,
        0,
        ctypes.byref(rect),
        0
    )
    return (rect.left, rect.top, rect.right, rect.bottom)

def set_work_area(left, top, right, bottom):
    """Set the system-wide desktop work area rect on Windows."""
    SPI_SETWORKAREA = 0x002F
    SPIF_SENDCHANGE = 0x02
    rect = RECT(left, top, right, bottom)
    ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETWORKAREA,
        0,
        ctypes.byref(rect),
        SPIF_SENDCHANGE
    )

def get_window_rect(hwnd):
    """Retrieve window coordinates and size in screen coordinates."""
    rect = RECT()
    try:
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
    except Exception:
        return 0, 0, 0, 0

def get_window_border_offsets(hwnd):
    """Determine the size of invisible resize borders on Windows 10/11."""
    rect_win = RECT()
    rect_dwm = RECT()
    try:
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect_win))
        # DWMWA_EXTENDED_FRAME_BOUNDS = 9
        hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd,
            9,
            ctypes.byref(rect_dwm),
            ctypes.sizeof(rect_dwm)
        )
        if hr == 0:  # S_OK
            left = rect_dwm.left - rect_win.left
            top = rect_dwm.top - rect_win.top
            right = rect_win.right - rect_dwm.right
            bottom = rect_win.bottom - rect_dwm.bottom
            return left, top, right, bottom
    except Exception:
        pass
    return 7, 0, 7, 7  # Fallback to standard Windows border measurements

def get_sorted_hmonitors():
    """Retrieve all active physical monitor handles sorted from left to right."""
    monitors = []
    
    def monitor_enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
        rect = lprcMonitor.contents
        monitors.append((rect.left, rect.top, hMonitor))
        return True
        
    MonitorEnumProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(RECT),
        ctypes.c_void_p
    )
    
    ctypes.windll.user32.EnumDisplayMonitors(None, None, MonitorEnumProc(monitor_enum_proc), 0)
    # Sort left-to-right, then top-to-bottom
    monitors.sort(key=lambda m: (m[0], m[1]))
    return [m[2] for m in monitors]

def get_screen_for_hwnd(hwnd, screens):
    """Determine the QScreen containing the window by index-matching sorted monitors."""
    # MONITOR_DEFAULTTONEAREST = 2
    hmonitor = ctypes.windll.user32.MonitorFromWindow(hwnd, 2)
    if not hmonitor:
        return screens[0]
        
    sorted_hmonitors = get_sorted_hmonitors()
    sorted_screens = sorted(screens, key=lambda s: (s.geometry().x(), s.geometry().y()))
    
    if hmonitor in sorted_hmonitors:
        idx = sorted_hmonitors.index(hmonitor)
        if idx < len(sorted_screens):
            return sorted_screens[idx]
            
    return screens[0]

def get_top_bar_height(screen):
    """Scan visible windows to detect any waybar-like top panel (including our own when visible) and return its height."""
    geom = screen.geometry()
    top_bar_h = 0
    
    def enum_cb(hwnd, lParam):
        nonlocal top_bar_h
        if IsWindowVisible(hwnd):
            # Check window title
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            title = ""
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                
            # Query class name
            class_name = ctypes.create_unicode_buffer(256)
            ctypes.windll.user32.GetClassNameW(hwnd, class_name, 256)
            cls = class_name.value
            
            rect = RECT()
            if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                
                # If it's our own TopbarWidget:
                if "TopbarWidget" in title:
                    # Only account for it if it is slid down (visible on screen)
                    if rect.top >= geom.y() and rect.bottom <= geom.y() + 80:
                        # TopbarWidget sits at y=4 with height=36, so total top offset is 40px
                        top_bar_h = max(top_bar_h, 40)
                    return True
                
                # Check for other status bars (e.g. Yasb, RetroBar, Komorebi Bar)
                is_bar = any(name in cls.lower() or name in title.lower() for name in ["yasb", "retrobar", "komorebi", "waybar", "appbar", "panel"])
                if is_bar or (w >= geom.width() * 0.8 and 20 <= h <= 80):
                    if abs(rect.top - geom.y()) <= 5:
                        top_bar_h = max(top_bar_h, h)
                        
        return True
        
    EnumWindows(EnumWindowsProc(enum_cb), 0)
    return top_bar_h

def get_screen_working_geom(screen):
    """Calculate monitor usable geometry, dynamically adjusting for the auto-hidden taskbar and top status bars."""
    geom = screen.geometry()
    
    # 1. Get native HMONITOR matching this screen
    hmonitor = None
    sorted_hmonitors = get_sorted_hmonitors()
    sorted_screens = sorted(QApplication.screens(), key=lambda s: (s.geometry().x(), s.geometry().y()))
    for idx, s in enumerate(sorted_screens):
        if s.name() == screen.name() and idx < len(sorted_hmonitors):
            hmonitor = sorted_hmonitors[idx]
            break
            
    # Default top bar height
    top_bar_h = 0
    
    # 2. Query OS work area difference for registered AppBars (PowerToys, retrobar, etc.)
    if hmonitor:
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if ctypes.windll.user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            # If the OS work area top is shifted, it's a docked topbar/AppBar!
            os_top_margin = info.rcWork.top - info.rcMonitor.top
            if os_top_margin > 0:
                # Convert physical coordinates back to logical pixels
                dpr = screen.devicePixelRatio()
                top_bar_h = max(top_bar_h, int(os_top_margin / dpr))
                
    # 3. Check for our own TopbarWidget (which doesn't register as an OS AppBar but is active)
    our_topbar_h = get_top_bar_height(screen)
    top_bar_h = max(top_bar_h, our_topbar_h)
    
    # 4. Query bottom taskbar coordinates
    hwnd_taskbar = ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None)
    visible_taskbar_h = 0
    if hwnd_taskbar:
        rect = RECT()
        if ctypes.windll.user32.GetWindowRect(hwnd_taskbar, ctypes.byref(rect)):
            screen_bottom = geom.y() + geom.height()
            # If the taskbar sits at the bottom of this screen
            if rect.top < screen_bottom and rect.bottom >= screen_bottom and rect.left < geom.x() + geom.width() and rect.right > geom.x():
                # Taskbar height that is visible on screen
                visible_taskbar_h = max(0, screen_bottom - rect.top)
                
    # We also clamp minimum value (e.g. 2px thin line when fully hidden)
    # So we only compensate if taskbar is expanded (> 5px)
    if visible_taskbar_h <= 5:
        visible_taskbar_h = 0
        
    adjusted_geom = QRectF(
        geom.x(),
        geom.y() + top_bar_h,
        geom.width(),
        geom.height() - visible_taskbar_h - top_bar_h
    ).toRect()
    return adjusted_geom

def is_cloaked(hwnd):
    """Determine if a window is cloaked (invisible on another virtual desktop or suspended)."""
    cloaked = ctypes.c_int(0)
    # DWMWA_CLOAKED = 14
    hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(
        hwnd,
        14,
        ctypes.byref(cloaked),
        ctypes.sizeof(cloaked)
    )
    if hr == 0:
        return bool(cloaked.value)
    return False

def calculate_dwindle_rects(x, y, w, h, n, gap=10):
    """Calculate Hyprland-style Dwindle (Fibonacci) tiling layout rects."""
    rects = []
    curr_x, curr_y, curr_w, curr_h = x, y, w, h
    
    for i in range(n):
        if i == n - 1:
            rects.append((curr_x, curr_y, curr_w, curr_h))
        else:
            if curr_w >= curr_h:
                # Split horizontally (vertical separator line)
                half_w = (curr_w - gap) // 2
                rects.append((curr_x, curr_y, half_w, curr_h))
                curr_x = curr_x + half_w + gap
                curr_w = curr_w - half_w - gap
            else:
                # Split vertically (horizontal separator line)
                half_h = (curr_h - gap) // 2
                rects.append((curr_x, curr_y, curr_w, half_h))
                curr_y = curr_y + half_h + gap
                curr_h = curr_h - half_h - gap
    return rects

def get_startup_file_path():
    import os
    startup_dir = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    return os.path.join(startup_dir, "caelestia.vbs")

def enable_autostart():
    import os
    path = get_startup_file_path()
    try:
        # Create VBScript file that launches caelestia invisibly on boot
        with open(path, "w") as f:
            f.write('Set WshShell = CreateObject("WScript.Shell")\n')
            f.write('WshShell.Run "powershell -WindowStyle Hidden -Command Start-Process caelestia -WindowStyle Hidden", 0, False\n')
        print("Autostart successfully enabled! Caelestia will start silently on boot.")
    except Exception as e:
        print(f"Error enabling autostart: {e}")

def disable_autostart():
    import os
    path = get_startup_file_path()
    try:
        if os.path.exists(path):
            os.remove(path)
            print("Autostart successfully disabled!")
        else:
            print("Autostart was not enabled.")
    except Exception as e:
        print(f"Error disabling autostart: {e}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Caelestia UI - Tiling Window Manager")
    parser.add_argument("--autostart", action="store_true", help="Enable autostart on Windows boot")
    parser.add_argument("--no-autostart", action="store_true", help="Disable autostart on Windows boot")
    args = parser.parse_known_args()[0]
    
    if args.autostart:
        enable_autostart()
        sys.exit(0)
    elif args.no_autostart:
        disable_autostart()
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    borders = []
    topbar = TopbarWidget()
    is_light_theme = True
    
    tiled_windows_by_screen = {}
    managed_hwnds = set()
    dragged_hwnd = None
    fullscreen_hwnds = set()
    
    def toggle_fullscreen_active_window():
        active_hwnd = ctypes.windll.user32.GetForegroundWindow()
        if not active_hwnd:
            return
        if is_tileable(active_hwnd) or active_hwnd in fullscreen_hwnds:
            if active_hwnd in fullscreen_hwnds:
                fullscreen_hwnds.discard(active_hwnd)
                if IsZoomed(active_hwnd):
                    ShowWindow(active_hwnd, 9)  # SW_RESTORE
            else:
                fullscreen_hwnds.add(active_hwnd)
                ShowWindow(active_hwnd, 3)  # SW_MAXIMIZE

    # Register Win+F (MOD_WIN = 0x0008, MOD_NOREPEAT = 0x4000, VK_F = 0x46) bound to the topbar widget's HWND
    ctypes.windll.user32.RegisterHotKey(int(topbar.winId()), 99, 0x0008 | 0x4000, 0x46)
    hotkey_filter = HotkeyFilter(toggle_fullscreen_active_window)
    app.installNativeEventFilter(hotkey_filter)
    
    # Cache the original work area to restore on exit
    original_work_area = get_work_area()
    
    def apply_custom_work_area():
        """Compute and set the custom work area matching the inner cutout region on the primary screen."""
        screen = app.primaryScreen()
        if screen:
            geom = get_screen_working_geom(screen)
            window_gap = 10
            # Symmetrical 10px margins on all sides (left, top, right, bottom)
            new_left = geom.x() + window_gap
            new_top = geom.y() + window_gap
            new_right = geom.x() + geom.width() - window_gap
            new_bottom = geom.y() + geom.height() - window_gap
            set_work_area(new_left, new_top, new_right, new_bottom)
            
    def restore_work_area():
        """Restore the cached Windows work area and clean up window regions."""
        ctypes.windll.user32.UnregisterHotKey(int(topbar.winId()), 99)
        if original_work_area:
            set_work_area(*original_work_area)
            
    def rebuild_borders():
        """Rebuild border widgets for all connected screens dynamically."""
        nonlocal borders, tiled_windows_by_screen
        for b in borders:
            b.hide()
            b.deleteLater()
        borders.clear()
        
        screens = app.screens()
        tiled_windows_by_screen = {screen: [] for screen in screens}
        
        for screen in screens:
            # Symmetrical 0px border width since edges are fully transparent, leaving only window_gap padding
            b = BorderWidget(screen, left_border=0, top_border=0, right_border=0, bottom_border=0, corner_radius=20, border_color="#00000000")
            borders.append(b)
            b.show()
            
        topbar.update_geometry()
        topbar.show()
        topbar.raise_()  # Ensure topbar stays on top of the primary screen's border
        
        apply_custom_work_area()

    # Rebuild borders on start and connect screen layout and theme changes
    rebuild_borders()
    app.screenAdded.connect(lambda _: rebuild_borders())
    app.screenRemoved.connect(lambda _: rebuild_borders())
    
    app.aboutToQuit.connect(restore_work_area)
    
    def is_tileable(hwnd):
        """Determine if a window handle represents a valid application window to tile."""
        # Check against all border windows and topbar
        our_hwnds = {int(b.winId()) for b in borders}
        our_hwnds.add(int(topbar.winId()))
        
        if hwnd in our_hwnds:
            return False
        # Exclude active Win+F fullscreen windows from tiling layout
        if hwnd in fullscreen_hwnds:
            return False
        if not IsWindowVisible(hwnd):
            return False
        if ctypes.windll.user32.IsIconic(hwnd):  # Minimized
            return False
        if is_cloaked(hwnd):  # Exclude cloaked windows (hidden on other desktops/suspended)
            return False
            
        # Must have a text title
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return False
            
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -16)  # GWL_STYLE
        style_ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
        
        # Check if the window is resizable (must have WS_THICKFRAME or WS_MAXIMIZEBOX)
        WS_THICKFRAME = 0x00040000
        WS_MAXIMIZEBOX = 0x00010000
        if not (style & WS_THICKFRAME) and not (style & WS_MAXIMIZEBOX):
            return False
            
        # Exclude windows already running in native fullscreen mode (e.g. games),
        # unless it is a window currently fullscreened by our Win+F hotkey.
        if hwnd not in fullscreen_hwnds:
            hmonitor = ctypes.windll.user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST = 2
            if hmonitor:
                info = MONITORINFO()
                info.cbSize = ctypes.sizeof(MONITORINFO)
                if ctypes.windll.user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                    rect = RECT()
                    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    w = rect.right - rect.left
                    h = rect.bottom - rect.top
                    mon_w = info.rcMonitor.right - info.rcMonitor.left
                    mon_h = info.rcMonitor.bottom - info.rcMonitor.top
                    if rect.left == info.rcMonitor.left and rect.top == info.rcMonitor.top and w == mon_w and h == mon_h:
                        return False
                        
        # Skip child windows
        WS_CHILD = 0x40000000
        if style & WS_CHILD:
            return False
            
        # Exclude tool windows (toolbars, tooltips, dialogs)
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_APPWINDOW = 0x00040000
        if (style_ex & WS_EX_TOOLWINDOW) and not (style_ex & WS_EX_APPWINDOW):
            return False
            
        # Exclude common system classes
        class_name = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetClassNameW(hwnd, class_name, 256)
        if class_name.value in ["Shell_TrayWnd", "Progman", "WorkerW", "Button", "ComboLBox", 
                                "Windows.UI.Core.CoreWindow", "EdgeUiInputWndClass", 
                                "TextInputBridgeClass", "GlassWndClass"]:
            return False
            
        # Ensure it has a reasonable size
        rect = RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        if (rect.right - rect.left) <= 100 or (rect.bottom - rect.top) <= 100:
            return False
            
        return True

    def tiling_manager_loop():
        nonlocal tiled_windows_by_screen, dragged_hwnd
        if not any(b.isVisible() for b in borders):
            return
            
        screens = app.screens()
        
        # Check if left mouse button is pressed (drag action)
        # VK_LBUTTON = 0x01
        l_button_down = bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
        
        # Enumerate visible application windows
        current_visible = []
        def enum_cb(hwnd, lParam):
            if is_tileable(hwnd):
                current_visible.append(hwnd)
            return True
        EnumWindows(EnumWindowsProc(enum_cb), 0)
        
        # Group current visible windows by screen using GDI physical monitor checks
        visible_by_screen = {screen: [] for screen in screens}
        for hwnd in current_visible:
            assigned_screen = get_screen_for_hwnd(hwnd, screens)
            visible_by_screen[assigned_screen].append(hwnd)
            
        # Dragging State Machine
        if l_button_down:
            if not dragged_hwnd:
                # Find if any managed window has been dragged away from its tile position
                for screen in screens:
                    border_w = next((b for b in borders if b.target_screen.name() == screen.name()), None)
                    if not border_w:
                        continue
                    geom = get_screen_working_geom(screen)
                    window_gap = 10
                    tx = geom.x() + window_gap
                    ty = geom.y() + window_gap
                    tw = geom.width() - (2 * window_gap)
                    th = geom.height() - (2 * window_gap)
                    
                    tiled = tiled_windows_by_screen.get(screen, [])
                    n = len(tiled)
                    if n > 0:
                        rects = calculate_dwindle_rects(tx, ty, tw, th, n, gap=10)
                        for i, hwnd in enumerate(tiled):
                            rx, ry, rw, rh = rects[i]
                            x, y, w, h = get_window_rect(hwnd)
                            # If mouse is down and window is dragged > 15px, start tracking it
                            if abs(x - rx) > 15 or abs(y - ry) > 15:
                                dragged_hwnd = hwnd
                                break
                    if dragged_hwnd:
                        break
        else:
            # Mouse released: Auto-fit the dragged window into the closest slot
            if dragged_hwnd:
                # Get drop center coordinates
                x, y, w, h = get_window_rect(dragged_hwnd)
                cx = x + w // 2
                cy = y + h // 2
                
                # Identify drop screen
                target_screen = get_screen_for_hwnd(dragged_hwnd, screens)
                
                # Remove dragged_hwnd from all screens first
                for s in screens:
                    tiled_windows_by_screen[s] = [hw for hw in tiled_windows_by_screen.get(s, []) if hw != dragged_hwnd]
                    
                tiled_list = tiled_windows_by_screen.get(target_screen, [])
                
                # Append to calculate closest target slots
                temp_list = list(tiled_list)
                temp_list.append(dragged_hwnd)
                n = len(temp_list)
                
                border_w = next((b for b in borders if b.target_screen.name() == target_screen.name()), None)
                if border_w:
                    geom = get_screen_working_geom(target_screen)
                    window_gap = 10
                    tx = geom.x() + window_gap
                    ty = geom.y() + window_gap
                    tw = geom.width() - (2 * window_gap)
                    th = geom.height() - (2 * window_gap)
                    
                    rects = calculate_dwindle_rects(tx, ty, tw, th, n, gap=10)
                    
                    # Find slot with the closest center coordinate
                    closest_idx = 0
                    min_dist = float('inf')
                    for i, (rx, ry, rw, rh) in enumerate(rects):
                        rcx = rx + rw // 2
                        rcy = ry + rh // 2
                        dist = (cx - rcx) ** 2 + (cy - rcy) ** 2
                        if dist < min_dist:
                            min_dist = dist
                            closest_idx = i
                            
                    # Insert dragged window at the closest slot
                    tiled_list.insert(closest_idx, dragged_hwnd)
                    tiled_windows_by_screen[target_screen] = tiled_list
                    managed_hwnds.add(dragged_hwnd)
                    
                dragged_hwnd = None
                
        # Run dwindle layout calculations independently for each screen
        for screen in screens:
            border_w = next((b for b in borders if b.target_screen.name() == screen.name()), None)
            if not border_w:
                continue
                
            # Get adjusted geometry taking taskbar into account
            geom = get_screen_working_geom(screen)
            window_gap = 10
            target_x = geom.x() + window_gap
            target_y = geom.y() + window_gap
            target_w = geom.width() - (2 * window_gap)
            target_h = geom.height() - (2 * window_gap)
            
            # Update the border widget's geometry dynamically so it shrinks with the taskbar
            border_w.setGeometry(geom)
            
            # If this is the primary screen, also update the top bar's geometry dynamically
            if screen.name() == app.primaryScreen().name():
                topbar.update_geometry(geom)
            
            # Get tiled list for this screen
            prev_tiled = tiled_windows_by_screen.get(screen, [])
            
            # Filter Z-order list to keep only currently visible windows on this screen
            new_tiled = [hwnd for hwnd in prev_tiled if hwnd in visible_by_screen[screen] and hwnd != dragged_hwnd]
            
            # Append new windows discovered on this screen
            for hwnd in visible_by_screen[screen]:
                if hwnd not in new_tiled and hwnd != dragged_hwnd:
                    new_tiled.append(hwnd)
            
            # Check if this screen has any fullscreen window active
            screen_fullscreen_hwnd = next((hwnd for hwnd in new_tiled if hwnd in fullscreen_hwnds), None)
            # Check if layout needs re-tiling (list changed, window maximized, or layout size changed due to taskbar growth)
            has_maximized = any(IsZoomed(hwnd) for hwnd in new_tiled)
            list_changed = (new_tiled != prev_tiled)
            
            # We track layout changes: if taskbar height changed, we force re-tiling to keep it smooth
            if list_changed or has_maximized or True:  # Continually enforce correct alignment
                tiled_windows_by_screen[screen] = new_tiled
                
                # Restore any maximized window
                for hwnd in new_tiled:
                    if IsZoomed(hwnd):
                        ShowWindow(hwnd, 9)  # SW_RESTORE
                        
                n = len(new_tiled)
                if n > 0:
                    rects = calculate_dwindle_rects(target_x, target_y, target_w, target_h, n, gap=10)
                    for i, hwnd in enumerate(new_tiled):
                        rx, ry, rw, rh = rects[i]
                        
                        l_off, t_off, r_off, b_off = get_window_border_offsets(hwnd)
                        adj_x = rx - l_off
                        adj_y = ry - t_off
                        adj_w = rw + l_off + r_off
                        adj_h = rh + t_off + b_off
                        
                        # Move window to match target layout
                        MoveWindow(hwnd, adj_x, adj_y, adj_w, adj_h, True)
                        managed_hwnds.add(hwnd)

        # Cleanup managed_hwnds and fullscreen_hwnds of closed/minimized windows
        for hwnd in list(fullscreen_hwnds):
            if not IsWindowVisible(hwnd) or ctypes.windll.user32.IsIconic(hwnd) or is_cloaked(hwnd):
                fullscreen_hwnds.discard(hwnd)
                
        all_tiled = []
        for s in screens:
            all_tiled.extend(tiled_windows_by_screen.get(s, []))
        if dragged_hwnd:
            all_tiled.append(dragged_hwnd)
            
        for hwnd in list(managed_hwnds):
            if hwnd not in all_tiled and hwnd not in fullscreen_hwnds:
                managed_hwnds.discard(hwnd)

    # Start the tiling manager loop with high-frequency ticks (50ms) for smooth taskbar tracking
    wm_timer = QTimer()
    wm_timer.timeout.connect(tiling_manager_loop)
    wm_timer.start(50)
    
    # System Tray setup
    tray_icon = QSystemTrayIcon(app)
    tray_icon.setIcon(app.style().standardIcon(app.style().StandardPixmap.SP_ComputerIcon))
    
    menu = QMenu()
    
    def toggle_border(checked):
        for b in borders:
            b.setVisible(checked)
        if checked:
            apply_custom_work_area()
        else:
            restore_work_area()
            
    def toggle_theme():
        nonlocal is_light_theme
        is_light_theme = not is_light_theme
        topbar.toggle_theme(is_light_theme)
            
    toggle_border_action = QAction("Toggle Border Padding", menu)
    toggle_border_action.setCheckable(True)
    toggle_border_action.setChecked(True)
    toggle_border_action.triggered.connect(toggle_border)
    
    toggle_theme_action = QAction("Toggle Theme (Light/Dark)", menu)
    toggle_theme_action.triggered.connect(toggle_theme)
    
    exit_action = QAction("Exit Caelestia UI", menu)
    exit_action.triggered.connect(app.quit)
    
    menu.addAction(toggle_border_action)
    menu.addAction(toggle_theme_action)
    menu.addSeparator()
    menu.addAction(exit_action)
    
    tray_icon.setContextMenu(menu)
    tray_icon.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
