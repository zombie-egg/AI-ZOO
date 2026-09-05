# Phase 2 相机与打印机测试台

## 当前实测状态（2026-08-27）

- Windows 已正常识别外接 `1200W Camera`，DirectShow 可见。
- 相机报告的静态高分辨率档为 MJPEG `4000×3000 @ 10–15fps`；另有 `2592×1944 @ 30fps`、`2048×1536 @ 30fps` 和 `1920×1080 @ 60fps` 等档位。
- 电脑同时存在 `HD Webcam`，所以采集程序必须按名称锁定 `1200W Camera`，不能依赖“第 0 个摄像头”。
- 本次只完成设备/模式探测，没有擅自拍一张现场画面；`hardware/test-bench.json` 中 `actual_frame_capture_verified=false`。
- Windows 打印机列表当前没有 Canon SELPHY CP1500，符合“尚未连接”的现场情况，不能写成真实出纸已通过。

## 相机建议测试档

- 最终拍照：`4000×3000 MJPEG @ 15fps`，取稳定后的单帧；12MP 足够给人脸质检和 2048px 母版。
- 实时取景：`1920×1080 MJPEG @ 30fps`，降低预览延迟。
- 拍摄时连续取 3 张，间隔 150–250ms；按单脸、亮度、模糊度和正脸角度选最佳一张，其余可作身份参考。
- 拍摄背景和补光要稳定。Prompt 的环境光融合不能弥补严重过曝、运动拖影或脸太小。

可用下面的命令再次查看设备能力（只读，不拍照）：

```powershell
ffmpeg -hide_banner -list_options true -f dshow -i video="1200W Camera"
```

## CP1500 临时测试规范

佳能中国官方规格确认：SELPHY CP1500 是染料热升华打印，最大 `300×300dpi`；明信片无边框成像尺寸 `100×148mm`，电脑连接口为 USB Type-C。Phase 2 的 `print_payload.html` 已据此设置页面，不再使用泛化的 101.6×152.4mm 美式 4×6 尺寸。

- 目标画布：`100×148mm`；按 300dpi 换算约 `1181×1748px`。
- 当前业务要求仍保留四周 3mm 白边和底部 2mm “AI 生成 · 订单号”小字。
- 接上打印机后必须补做：驱动纸型选择、横竖方向、系统是否二次缩放、白边实际毫米数、肤色色偏、暗部层次、连续 10 张进出纸。
- 真正商业打印机更换时只新增 printer profile，不改终图和订单协议。

官方依据：[佳能中国 CP1500 产品规格](https://www.canon.com.cn/product/cp1500/spec.html)、[佳能中国 CP1500 对应耗材](https://m.canon.com.cn/product/cp1500/supply.html)。

