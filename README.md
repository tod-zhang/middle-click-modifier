# 🖱️ Middle Click Modifier

Map the middle mouse button to **Left Ctrl + Left Shift** modifier keys.

将鼠标中键映射为 **Left Ctrl + Left Shift** 组合键。

## Features | 功能

| Action | Effect |
|--------|--------|
| Hold middle button | Acts as holding `Left Ctrl` + `Left Shift` |
| Release middle button | Releases the modifier keys |
| Right-click tray icon | Toggle auto-start / Exit |

## Install & Run | 安装 & 运行

```bash
# Install dependencies
pip install -r requirements.txt

# Run (choose one)
python middle_click_modifier.py   # Console window auto-hides
pythonw middle_click_modifier.py  # No window at all
# Or double-click run.bat
```

## Exit | 退出

Right-click the system tray icon → click **退出 (Exit)**

## Auto-Start | 开机自启动

Right-click the system tray icon → check **开机自启动** (writes to registry `HKCU\...\Run`, uncheck to remove)

## Requirements | 系统要求

- Windows 10/11
- Python 3.6+
- pystray, pillow

## License

[MIT](LICENSE)
