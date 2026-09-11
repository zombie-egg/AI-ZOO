const CAMERA_ALIASES = ['decxin', '1200w', 'uvc', 'usb camera', 'webcam', 'camera']

function cameraMatches(camera, preferredLabel = '') {
  const label = String(camera?.label || '').toLowerCase()
  const wanted = String(preferredLabel || '').trim().toLowerCase()
  return Boolean(label) && (label.includes(wanted) || CAMERA_ALIASES.some((alias) => label.includes(alias)))
}

function describeCameraError(error, cameras) {
  const names = cameras.map((camera) => camera.label || '未命名 USB 摄像头').join('、')
  if (error?.name === 'NotAllowedError') return '浏览器未获准使用摄像头。请在地址栏的摄像头权限中选择“允许”，然后刷新页面'
  if (error?.name === 'NotFoundError') return 'Windows 没有向浏览器提供可用摄像头。请检查 DECXIN 的 USB 连接和 Windows“相机”应用是否能打开它'
  if (error?.name === 'NotReadableError') return 'DECXIN 正被 Windows 相机、微信或其他程序占用。请关闭占用程序后重试'
  if (error?.name === 'OverconstrainedError') return '当前 DECXIN 视频规格不被浏览器支持，已尝试自动降级但仍未成功'
  return `${error?.message || '摄像头启动失败'}${names ? `（已检测到：${names}）` : ''}`
}

async function requestCamera(constraints) {
  return navigator.mediaDevices.getUserMedia({ audio: false, video: constraints })
}

export async function openPreferredCamera(videoElement, preferredLabel) {
  if (!navigator.mediaDevices?.getUserMedia || !navigator.mediaDevices?.enumerateDevices) {
    throw new Error('此浏览器不支持摄像头访问，请使用最新版 Microsoft Edge 或 Chrome')
  }

  let permissionStream
  try {
    // Windows keeps USB-device labels hidden until the first permission prompt.
    // Open the most compatible UVC stream first, then immediately switch to DECXIN.
    permissionStream = await requestCamera(true)
  } catch (error) {
    throw new Error(describeCameraError(error, []))
  }

  let cameras = []
  try {
    cameras = (await navigator.mediaDevices.enumerateDevices()).filter((item) => item.kind === 'videoinput')
  } finally {
    permissionStream.getTracks().forEach((track) => track.stop())
  }
  if (!cameras.length) throw new Error('没有找到可用摄像头，请检查 DECXIN 的 USB 连接')

  const preferred = cameras.find((camera) => cameraMatches(camera, preferredLabel))
  const candidates = [preferred, ...cameras.filter((camera) => camera.deviceId !== preferred?.deviceId)].filter(Boolean)
  let stream
  let lastError
  for (const camera of candidates) {
    try {
      // Do not set facingMode: many desktop DECXIN/UVC drivers reject it.
      stream = await requestCamera({
        deviceId: { exact: camera.deviceId },
        width: { ideal: 1920 },
        height: { ideal: 1080 },
        frameRate: { ideal: 30, max: 30 },
      })
      break
    } catch (error) {
      lastError = error
    }
  }
  if (!stream) throw new Error(describeCameraError(lastError, cameras))

  try {
    videoElement.srcObject = stream
    await videoElement.play()
  } catch (error) {
    stream.getTracks().forEach((track) => track.stop())
    throw new Error(describeCameraError(error, cameras))
  }
  const track = stream.getVideoTracks()[0]
  const settings = track?.getSettings?.() || {}
  stream.kioskDeviceLabel = track?.label || preferred?.label || 'USB 摄像头'
  stream.kioskResolution = `${settings.width || videoElement.videoWidth}×${settings.height || videoElement.videoHeight}`
  return stream
}

async function videoFrameBlob(videoElement) {
  const canvas = document.createElement('canvas')
  canvas.width = videoElement.videoWidth || 1920
  canvas.height = videoElement.videoHeight || 1080
  canvas.getContext('2d', { alpha: false }).drawImage(videoElement, 0, 0, canvas.width, canvas.height)
  return await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.95))
}

// Draw the frame before JPEG encoding so the captured moment is exactly when
// the countdown reaches zero, independent of USB still-photo latency.
export async function captureInstantJpeg(videoElement) {
  return videoFrameBlob(videoElement)
}

async function stillPhotoBlob(stream, videoElement) {
  const track = stream?.getVideoTracks?.()[0]
  if (track && 'ImageCapture' in window) {
    try {
      const capture = new window.ImageCapture(track)
      return await capture.takePhoto()
    } catch {
      // Some USB UVC drivers expose ImageCapture but reject takePhoto; retain a high-res frame fallback.
    }
  }
  return videoFrameBlob(videoElement)
}

async function sharpnessScore(blob) {
  const bitmap = await createImageBitmap(blob)
  const width = 320
  const height = Math.max(180, Math.round(width * bitmap.height / bitmap.width))
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d', { willReadFrequently: true })
  context.drawImage(bitmap, 0, 0, width, height)
  bitmap.close()
  const pixels = context.getImageData(0, 0, width, height).data
  let score = 0
  for (let y = 1; y < height - 1; y += 2) {
    for (let x = 1; x < width - 1; x += 2) {
      const index = (y * width + x) * 4
      const left = index - 4
      const right = index + 4
      const above = index - width * 4
      const below = index + width * 4
      const gray = (offset) => pixels[offset] * 0.299 + pixels[offset + 1] * 0.587 + pixels[offset + 2] * 0.114
      score += Math.abs(gray(left) - gray(right)) + Math.abs(gray(above) - gray(below))
    }
  }
  return score
}

async function normalizeJpeg(blob) {
  if (blob.type === 'image/jpeg') return blob
  const bitmap = await createImageBitmap(blob)
  const canvas = document.createElement('canvas')
  canvas.width = bitmap.width
  canvas.height = bitmap.height
  canvas.getContext('2d', { alpha: false }).drawImage(bitmap, 0, 0)
  bitmap.close()
  return await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.95))
}

export async function captureBestJpeg(videoElement, stream, count = 3) {
  const candidates = []
  for (let index = 0; index < count; index += 1) {
    const blob = await stillPhotoBlob(stream, videoElement)
    candidates.push({ blob, score: await sharpnessScore(blob) })
    if (index < count - 1) await new Promise((resolve) => setTimeout(resolve, 180))
  }
  candidates.sort((first, second) => second.score - first.score)
  return normalizeJpeg(candidates[0].blob)
}

export function stopCamera(stream) {
  stream?.getTracks().forEach((track) => track.stop())
}
