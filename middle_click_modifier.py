"""
Middle Click Modifier - 鼠标中键映射为 Ctrl+Shift
====================================================
按住鼠标中键 = 按住 Left Ctrl + Left Shift
松开鼠标中键 = 释放 Ctrl + Shift

系统托盘运行，右键托盘图标可切换开机自启动或退出。
"""

import ctypes
import ctypes.wintypes
import sys
import os
import threading
import winreg
import atexit

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    print("缺少依赖，正在安装...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pystray", "pillow", "-q"])
    import pystray
    from PIL import Image, ImageDraw

# ═══════════════════════════════════════════════════════════════════
#  Windows API 常量 & 结构体
# ═══════════════════════════════════════════════════════════════════
WH_MOUSE_LL = 14
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_QUIT = 0x0012
KEYEVENTF_KEYUP = 0x0002
VK_LCONTROL = 0xA2
VK_LSHIFT = 0xA0
SW_HIDE = 0

ULONG_PTR = ctypes.POINTER(ctypes.c_ulong)


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", ctypes.wintypes.POINT),
        ("mouseData", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(
    ctypes.c_long, ctypes.c_int,
    ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM,
)

# ═══════════════════════════════════════════════════════════════════
#  Windows API 函数签名
# ═══════════════════════════════════════════════════════════════════
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int, HOOKPROC, ctypes.wintypes.HINSTANCE, ctypes.wintypes.DWORD,
]
user32.SetWindowsHookExW.restype = ctypes.c_void_p

user32.CallNextHookEx.argtypes = [
    ctypes.c_void_p, ctypes.c_int,
    ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM,
]
user32.CallNextHookEx.restype = ctypes.c_long

user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
user32.UnhookWindowsHookEx.restype = ctypes.wintypes.BOOL

user32.GetMessageW.argtypes = [
    ctypes.POINTER(ctypes.wintypes.MSG),
    ctypes.wintypes.HWND, ctypes.c_uint, ctypes.c_uint,
]
user32.GetMessageW.restype = ctypes.wintypes.BOOL

user32.keybd_event.argtypes = [
    ctypes.wintypes.BYTE, ctypes.wintypes.BYTE,
    ctypes.wintypes.DWORD, ctypes.POINTER(ctypes.c_ulong),
]
user32.keybd_event.restype = None

user32.PostThreadMessageW.argtypes = [
    ctypes.wintypes.DWORD, ctypes.c_uint,
    ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM,
]
user32.PostThreadMessageW.restype = ctypes.wintypes.BOOL

user32.ShowWindow.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = ctypes.wintypes.BOOL

kernel32.GetModuleHandleW.argtypes = [ctypes.wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = ctypes.wintypes.HMODULE

kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = ctypes.wintypes.DWORD

kernel32.GetConsoleWindow.argtypes = []
kernel32.GetConsoleWindow.restype = ctypes.wintypes.HWND

# ═══════════════════════════════════════════════════════════════════
#  全局状态
# ═══════════════════════════════════════════════════════════════════
APP_NAME = "MiddleClickModifier"
REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

hook_handle = None
hook_thread_id = None
is_modifier_active = False
_hook_callback = None  # prevent GC of the callback


# ═══════════════════════════════════════════════════════════════════
#  键盘模拟
# ═══════════════════════════════════════════════════════════════════
def press_modifiers():
    user32.keybd_event(VK_LCONTROL, 0x1D, 0, None)
    user32.keybd_event(VK_LSHIFT, 0x2A, 0, None)


def release_modifiers():
    user32.keybd_event(VK_LSHIFT, 0x2A, KEYEVENTF_KEYUP, None)
    user32.keybd_event(VK_LCONTROL, 0x1D, KEYEVENTF_KEYUP, None)


# ═══════════════════════════════════════════════════════════════════
#  鼠标钩子
# ═══════════════════════════════════════════════════════════════════
def mouse_hook_proc(nCode, wParam, lParam):
    global is_modifier_active

    if nCode >= 0:
        if wParam == WM_MBUTTONDOWN:
            if not is_modifier_active:
                is_modifier_active = True
                press_modifiers()
            return 1

        elif wParam == WM_MBUTTONUP:
            if is_modifier_active:
                is_modifier_active = False
                release_modifiers()
            return 1

    return user32.CallNextHookEx(hook_handle, nCode, wParam, lParam)


def hook_thread_func():
    """在独立线程中运行鼠标钩子 + 消息循环"""
    global hook_handle, hook_thread_id, _hook_callback

    hook_thread_id = kernel32.GetCurrentThreadId()
    _hook_callback = HOOKPROC(mouse_hook_proc)
    h_module = kernel32.GetModuleHandleW(None)
    hook_handle = user32.SetWindowsHookExW(WH_MOUSE_LL, _hook_callback, h_module, 0)

    if not hook_handle:
        return

    msg = ctypes.wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        pass

    # 线程结束时清理
    if is_modifier_active:
        release_modifiers()
    if hook_handle:
        user32.UnhookWindowsHookEx(hook_handle)
        hook_handle = None


def stop_hook():
    """停止钩子线程"""
    global hook_handle, is_modifier_active

    if is_modifier_active:
        release_modifiers()
        is_modifier_active = False

    if hook_thread_id:
        user32.PostThreadMessageW(hook_thread_id, WM_QUIT, 0, 0)


# ═══════════════════════════════════════════════════════════════════
#  开机自启动 (注册表)
# ═══════════════════════════════════════════════════════════════════
def _get_autostart_command():
    script_path = os.path.abspath(__file__)
    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, "pythonw.exe")
    exe = pythonw if os.path.exists(pythonw) else sys.executable
    return f'"{exe}" "{script_path}"'


def is_autostart_enabled():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REGISTRY_KEY, 0, winreg.KEY_READ
        )
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except OSError:
        return False


def set_autostart(enabled):
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REGISTRY_KEY, 0, winreg.KEY_SET_VALUE
        )
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _get_autostart_command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except OSError:
                pass
        winreg.CloseKey(key)
    except OSError:
        pass


# ═══════════════════════════════════════════════════════════════════
#  系统托盘图标
# ═══════════════════════════════════════════════════════════════════
def create_tray_icon_image():
    """绘制一个鼠标图标，中键高亮绿色"""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 鼠标主体
    d.rounded_rectangle([12, 2, 52, 60], radius=14, fill="#37474F", outline="#B0BEC5", width=2)

    # 按键分割线
    d.line([(32, 2), (32, 30)], fill="#B0BEC5", width=1)

    # 中键 (滚轮) - 绿色高亮
    d.rounded_rectangle([26, 10, 38, 24], radius=3, fill="#4CAF50", outline="#81C784", width=1)

    # 按键区域与主体分界线
    d.line([(14, 30), (50, 30)], fill="#B0BEC5", width=1)

    return img


def build_tray(on_exit_callback):
    """构建系统托盘菜单"""

    def on_toggle_autostart(icon, item):
        set_autostart(not is_autostart_enabled())

    def autostart_checked(item):
        return is_autostart_enabled()

    def on_exit(icon, item):
        on_exit_callback()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("开机自启动", on_toggle_autostart, checked=autostart_checked),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("退出", on_exit),
    )

    return pystray.Icon(
        APP_NAME,
        create_tray_icon_image(),
        "鼠标中键 → Ctrl+Shift",
        menu,
    )


# ═══════════════════════════════════════════════════════════════════
#  主入口
# ═══════════════════════════════════════════════════════════════════
def main():
    # 隐藏控制台窗口（如果有）
    console = kernel32.GetConsoleWindow()
    if console:
        user32.ShowWindow(console, SW_HIDE)

    # 启动钩子线程
    hook_thread = threading.Thread(target=hook_thread_func, daemon=True)
    hook_thread.start()

    # 等待钩子初始化
    import time
    time.sleep(0.3)

    if not hook_handle:
        ctypes.windll.user32.MessageBoxW(
            None, "鼠标钩子安装失败！\n请尝试以管理员身份运行。",
            APP_NAME, 0x10,
        )
        sys.exit(1)

    # 运行系统托盘（阻塞主线程）
    tray = build_tray(on_exit_callback=stop_hook)
    tray.run()


if __name__ == "__main__":
    main()
