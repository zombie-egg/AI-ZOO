import { io } from 'socket.io-client'
import { kioskConfig } from '../config'

let socket
let activePrinterName = kioskConfig.printerName
const terminalStorageKey = 'ai-zoo-print-terminal'

function validTerminalId(value = '') {
  return /^[A-Za-z0-9_-]{32,128}$/.test(String(value))
}

export function resolveTerminalId() {
  const params = new URLSearchParams(globalThis.location?.search || '')
  const supplied = params.get('terminal') || ''
  if (validTerminalId(supplied)) {
    globalThis.localStorage?.setItem(terminalStorageKey, supplied)
    params.delete('terminal')
    const query = params.toString()
    globalThis.history?.replaceState({}, '', `${globalThis.location.pathname}${query ? `?${query}` : ''}${globalThis.location.hash}`)
    return supplied
  }
  const stored = globalThis.localStorage?.getItem(terminalStorageKey) || ''
  return validTerminalId(stored) ? stored : ''
}

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
  const terminalId = resolveTerminalId()
  if (!terminalId) {
    onStatus?.({ online: false, paired: false, message: '此电脑尚未安装或绑定后台打印服务' })
    return null
  }
  socket = io(kioskConfig.printRelayUrl, {
    path: kioskConfig.printRelayPath,
    transports: ['websocket'],
    auth: { role: 'kiosk', terminalId },
    reconnection: true,
  })
  socket.on('connect', () => {
    onStatus?.({ online: false, paired: true, message: '正在等待后台打印服务' })
    socket.emit('refreshPrinterList')
  })
  socket.on('agentStatus', (state) => {
    const agentOnline = Boolean(state?.online)
    onStatus?.({ online: false, paired: true, message: agentOnline ? '正在检测本机打印机' : '后台打印服务离线' })
    if (agentOnline) socket.emit('refreshPrinterList')
  })
  socket.on('disconnect', () => onStatus?.({ online: false, paired: true, message: '云端打印中转已断开' }))
  socket.on('connect_error', (error) => onStatus?.({ online: false, paired: true, message: error?.message || '云端打印中转连接失败' }))
  socket.on('printerList', (printers) => {
    activePrinterName = resolvePrinterName(printers)
    const online = Array.isArray(printers) && printers.length > 0
    onStatus?.({ online, paired: true, printers, printerName: activePrinterName, message: online ? '相机与打印已就绪' : '未检测到本机打印机' })
  })
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
