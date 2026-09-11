import { kioskConfig } from '../config'

async function request(path, options = {}) {
  const response = await fetch(`${kioskConfig.apiBaseUrl}${path}`, {
    credentials: 'include',
    headers: { Accept: 'application/json', ...(options.headers || {}) },
    ...options,
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok || (Object.prototype.hasOwnProperty.call(payload, 'code') && payload.code !== 1)) {
    throw new Error(payload.msg || payload.message || `请求失败（${response.status}）`)
  }
  return payload.data ?? payload
}

export const kioskApi = {
  getScenes() { return request('/api/kiosk/scenes') },
  createOrder(data) {
    return request('/api/kiosk/create-order', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
    })
  },
  recordConsent(orderId, data) {
    return request(`/api/kiosk/order-photos/${orderId}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'consent', ...data }),
    })
  },
  selectScene(orderId, sceneId) {
    return request(`/api/kiosk/order-scene/${orderId}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ scene_id: sceneId }),
    })
  },
  selectPose(orderId, poseId) {
    return request(`/api/kiosk/order-pose/${orderId}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pose_id: poseId }),
    })
  },
  uploadPhoto(orderId, file, shotType, participantNo = 1) {
    const body = new FormData()
    body.append('photo', file, `${shotType}.jpg`)
    body.append('shot_type', shotType)
    body.append('participant_no', String(participantNo))
    return request(`/api/kiosk/order-photos/${orderId}`, { method: 'POST', body })
  },
  getStatus(orderId) { return request(`/api/kiosk/order-status/${orderId}`) },
  createPayment(orderId, sku = 'print_1') {
    return request(`/api/kiosk/order-pay/${orderId}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ sku }),
    })
  },
  simulatePayment(orderId) {
    return request(`/api/kiosk/order-pay/${orderId}/simulate`, { method: 'POST' })
  },
  startGeneration(orderId, operatorTest = false, sku = 'print_1') {
    return request(`/api/kiosk/order-generate/${orderId}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ operator_test: operatorTest, sku }),
    })
  },
  getGenerationStatus(orderId) { return request(`/api/kiosk/order-generation-status/${orderId}`) },
  approveResult(orderId) {
    return request(`/api/kiosk/order-approve/${orderId}`, { method: 'POST' })
  },
  getPrintStatus(orderId) { return request(`/api/kiosk/order-print-status/${orderId}`) },
  reportPrintStatus(orderId, status, detail = '') {
    return request(`/api/kiosk/order-print-status/${orderId}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status, detail }),
    })
  },
}
