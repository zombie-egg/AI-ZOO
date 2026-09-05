export async function openPreferredCamera(videoElement, preferredLabel) {
  let devices = await navigator.mediaDevices.enumerateDevices()
  if (!devices.some((item) => item.kind === 'videoinput' && item.label)) {
    const permissionStream = await navigator.mediaDevices.getUserMedia({ audio: false, video: true })
    permissionStream.getTracks().forEach((track) => track.stop())
    devices = await navigator.mediaDevices.enumerateDevices()
  }
  const cameras = devices.filter((item) => item.kind === 'videoinput')
  const preferred = cameras.find((item) => item.label.includes(preferredLabel))
  if (!preferred && preferredLabel) {
    throw new Error(`没有找到指定摄像头“${preferredLabel}”，当前可用：${cameras.map((item) => item.label || '未命名摄像头').join('、')}`)
  }
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: false,
    video: {
      deviceId: preferred?.deviceId ? { exact: preferred.deviceId } : undefined,
      width: { ideal: 3840 },
      height: { ideal: 2160 },
      frameRate: { ideal: 30 },
      facingMode: 'user',
    },
  })
  videoElement.srcObject = stream
  await videoElement.play()
  const track = stream.getVideoTracks()[0]
  const settings = track?.getSettings?.() || {}
  stream.kioskDeviceLabel = preferred?.label || track?.label || '默认摄像头'
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
