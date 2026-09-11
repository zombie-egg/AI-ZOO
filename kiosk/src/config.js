const env = import.meta.env

export const kioskConfig = Object.freeze({
  localOperatorMode: String(env.VITE_KIOSK_LOCAL_OPERATOR_MODE ?? 'false').toLowerCase() === 'true',
  apiBaseUrl: String(env.VITE_API_BASE_URL ?? '').replace(/\/$/, ''),
  printRelayUrl: env.VITE_PRINT_RELAY_URL ?? globalThis.location?.origin ?? '',
  printRelayPath: env.VITE_PRINT_RELAY_PATH ?? '/print-relay/socket.io',
  printerName: env.VITE_PHOTO_PRINTER_NAME ?? 'Canon_SELPHY_CP1500',
  printPageWidthMm: Number(env.VITE_PRINT_PAGE_WIDTH_MM ?? 89),
  printPageHeightMm: Number(env.VITE_PRINT_PAGE_HEIGHT_MM ?? 119),
  // DECXIN is the field camera. camera.js also recognises common UVC aliases so
  // replacing the USB camera does not require a kiosk rebuild.
  cameraLabel: env.VITE_CAMERA_DEVICE_LABEL ?? 'DECXIN',
  price: 9.9,
  inactivityMs: Number(env.VITE_INACTIVITY_MS ?? 5 * 60 * 1000),
})
