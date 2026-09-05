import { io } from 'socket.io-client'
import { kioskConfig } from '../config'

let socket

export function connectPrintAgent(onStatus) {
  if (!kioskConfig.printAgentToken) return null
  socket = io(kioskConfig.printAgentUrl, {
    transports: ['websocket'], auth: { token: kioskConfig.printAgentToken }, reconnection: true,
  })
  socket.on('connect', () => onStatus?.({ online: true, message: '打印代理在线' }))
  socket.on('disconnect', () => onStatus?.({ online: false, message: '打印代理离线' }))
  socket.on('printerList', (printers) => onStatus?.({ online: true, printers }))
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
      html, templateId: orderNo, printer: kioskConfig.printerName,
      // CP1500 明信片纸是 100×148 mm；实际驱动边距须现场打一张校准。
      pageSize: { width: 100000, height: 148000, unit: '' },
      // 防止 Chromium 或驱动尺寸取整后意外产生第二页、浪费相纸。
      pageRanges: { from: 0, to: 0 }, copies, rePrintAble: true,
    })
  })
}

export function closePrintAgent() { socket?.disconnect() }
