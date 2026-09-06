const env = import.meta.env

export const kioskConfig = Object.freeze({
  localOperatorMode: String(env.VITE_KIOSK_LOCAL_OPERATOR_MODE ?? 'false').toLowerCase() === 'true',
  apiBaseUrl: String(env.VITE_API_BASE_URL ?? '').replace(/\/$/, ''),
  printAgentUrl: env.VITE_PRINT_AGENT_URL ?? 'http://127.0.0.1:17521',
  printAgentToken: env.VITE_PRINT_AGENT_TOKEN ?? '',
  printerName: env.VITE_PHOTO_PRINTER_NAME ?? 'Canon SELPHY CP1500',
  cameraLabel: env.VITE_CAMERA_DEVICE_LABEL ?? '1200W Camera',
  price: 9.9,
  inactivityMs: Number(env.VITE_INACTIVITY_MS ?? 5 * 60 * 1000),
})
