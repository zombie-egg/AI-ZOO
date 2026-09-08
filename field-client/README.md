# AI ZOO 现场电脑

每台现场电脑接好 USB 摄像头与打印机后，运行对应启动脚本。脚本会打开与新服务器同一套的 Kiosk 界面，摄像头与打印任务仍在现场电脑执行。

- macOS：双击 `start-macos.command`。首次运行时允许 Chrome 使用摄像头，并允许 Electron 打印。
- Windows：把 `start-windows.cmd` 复制到电脑后双击即可。脚本只使用 Windows 自带 PowerShell，会请求一次管理员权限，并自动：
  - 扫描 USB 打印机、启动打印服务并把 Canon SELPHY CP1500 设为默认打印机；
  - 下载便携版 Node.js 和 AI ZOO 打印代理，无需预装 Node、Git、Python；
  - 生成该电脑专属终端 ID，绑定服务器域名；
  - 添加开机自启，并在桌面创建 `AI ZOO Photo Kiosk` 快捷方式；
  - 打开 Kiosk。首次拍照时只需允许浏览器使用摄像头。

Windows 的自动配置文件保存在 `%LOCALAPPDATA%\AI-ZOO`，打印日志为 `%LOCALAPPDATA%\AI-ZOO\print-agent.log`。Canon 官方保证 CP1500 的电脑 USB 打印环境为 Windows 11。如果 Windows 11 没有自动建立打印队列，脚本会打开“打印机和扫描仪”设置页；保持 CP1500 开机并点击“添加设备”即可，不需要重新运行网页服务。

摄像头优先选择配置名称，找不到时自动使用系统默认摄像头。打印脚本只自动绑定 Canon SELPHY CP1500，避免误把照片发给办公室的其他打印机。
