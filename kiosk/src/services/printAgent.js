import { io } from 'socket.io-client'
import { kioskConfig } from '../config'

let socket
let activePrinterName = kioskConfig.printerName

function normalizePrinterName(value = '') {
  return String(value).toLowerCase().replace(/[^a-z0-9]+/g, '')
}

function resolvePrinterName(printers = []) {
  const configured = normalizePrinterName(kioskConfig.printerName)
  const candidates = Array.isArray(printers) ? printers : []
  const exact = candidates.find((printer) => normalizePrinterName(printer?.name) === configured)
  const selphy = candidates.find((printer) => normalizePrinterName(printer?.name).includes('canonselphycp1500'))
  const systemDefault = candidates.find((printer) => printer?.isDefault)
  return exact?.name || selphy?.name || systemDefault?.name || candidates[0]?.name || kioskConfig.printerName
}

export function connectPrintAgent(onStatus) {
  const auth = kioskConfig.printAgentToken ? { token: kioskConfig.printAgentToken } : undefined
  socket = io(kioskConfig.printAgentUrl, {
    transports: ['websocket'], auth, reconnection: true,
  })
  socket.on('connect', () => onStatus?.({ online: true, message: '打印代理在线' }))
  socket.on('disconnect', () => onStatus?.({ online: false, message: '打印代理离线' }))
  socket.on('connect_error', (error) => onStatus?.({ online: false, message: error?.message || '打印代理连接失败' }))
  socket.on('printerList', (printers) => {
    activePrinterName = resolvePrinterName(printers)
    onStatus?.({ online: true, printers, printerName: activePrinterName })
  })
  socket.emit('refreshPrinterList')
  return socket
}

export function printPhoto({ html, orderNo, copies = 1 }) {
  if (!socket?.connected) throw new Error('打印代理未连接')
  return new Promise((resolve, reject) => {
    const matches = (payload) => !payload?.templateId || String(payload.templateId) === String(orderNo)
    const cleanup = () => { socket.off('success', success); socket.off('error', failure); clearTimeout(timeout) }
    const success = (payload) => { if (matches(payload)) { cleanup(); resolve(payload) } }
    const failure = (payload) => { if (matches(payload)) { cleanup(); reject(new Error(payload?.message || payload?.msg || '打印失败')) } }
    const timeout = setTimeout(() => { cleanup(); reject(new Error('90 秒内未收到打印完成回调')) }, 90000)
    socket.on('success', success)
    socket.on('error', failure)
    socket.emit('news', {
      html, templateId: orderNo, printer: activePrinterName,
      // 当前现场使用 CP1500 KL 系列 L 尺寸相纸（89×119 mm）。
      // 保留环境变量覆盖，以便换成 KP 明信片纸时改为 100×148，而无需改代码。
      pageSize: {
        width: Math.round(kioskConfig.printPageWidthMm * 1000),
        height: Math.round(kioskConfig.printPageHeightMm * 1000),
        unit: '',
      },
      // 防止 Chromium 或驱动尺寸取整后意外产生第二页、浪费相纸。
      pageRanges: { from: 0, to: 0 }, copies, rePrintAble: true,
    })
  })
}

export function closePrintAgent() { socket?.disconnect() }
