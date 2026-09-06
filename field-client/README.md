# AI ZOO 现场电脑

每台现场电脑只需安装 Node.js 20+、USB 摄像头和打印机的系统驱动，再运行对应启动脚本。脚本会打开与新服务器同一套的 Kiosk 界面，摄像头与打印任务仍在现场电脑执行。

- macOS：双击 `start-macos.command`。首次运行时允许 Chrome 使用摄像头，并允许 Electron 打印。
- Windows：双击 `start-windows.cmd`。首次运行时允许浏览器使用摄像头。

摄像头优先选择配置名称，找不到时自动使用系统默认摄像头。打印机优先选择 Canon SELPHY CP1500，找不到时自动使用系统默认打印机。
