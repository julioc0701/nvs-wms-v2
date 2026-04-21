import { config } from '../config'

const BASE = config.endpoints.apiRoot

async function req(method, path, body, isForm = false) {
  const opts = { method, headers: {} }
  if (body) {
    if (isForm) {
      opts.body = body
    } else {
      opts.headers['Content-Type'] = 'application/json'
      opts.body = JSON.stringify(body)
    }
  }
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  return res.json()
}

export const api = {
  // Operators
  getOperators: () => req('GET', '/operators/'),
  getOperatorByBadge: (badge) => req('GET', `/operators/badge/${badge}`),
  createOperator: (name, badge, pin_code) => req('POST', '/operators/', { name, badge, pin_code }),
  updateOperatorPin: (id, pinCode) => req('PUT', `/operators/${id}/pin`, { pin_code: pinCode }),
  deleteOperator: (id) => req('DELETE', `/operators/${id}`),
  loginOperator: (operatorId, pinCode) => req('POST', '/operators/login', { operator_id: operatorId, pin_code: pinCode }),

  // Sessions
  getSessions: () => req('GET', '/sessions/'),
  getSession: (id) => req('GET', `/sessions/${id}`),
  getItems: (id) => req('GET', `/sessions/${id}/items`),
  uploadSession: (formData) => req('POST', '/sessions/upload', formData, true),
  listBatches: () => req('GET', '/sessions/batches'),
  archiveBatch: (batchId) => req('POST', `/sessions/batches/${batchId}/archive`),
  claimSession: (sessionId, operatorId) => req('POST', `/sessions/${sessionId}/claim`, { operator_id: operatorId }),
  deleteSession: (sessionId) => req('DELETE', `/sessions/${sessionId}`),
  reopenSession: (sessionId) => req('POST', `/sessions/${sessionId}/reopen-session`),
  findByBarcode: (barcode, operatorId) =>
    req('GET', `/sessions/find-by-barcode?barcode=${encodeURIComponent(barcode)}&operator_id=${operatorId}`),
  getShortageReport: () => req('GET', '/sessions/shortage-report'),
  getAllPendingItems: () => req('GET', '/sessions/all-pending'),
  transferItem: (itemId, operatorId) => req('POST', '/sessions/transfer', { item_id: itemId, operator_id: operatorId }),
  updateItemNotes: (itemId, notes) => req('PATCH', `/sessions/items/${itemId}/notes`, { notes }),
  updateShortageNotes: (sku, notes) => req('PATCH', `/sessions/shortage-report/${encodeURIComponent(sku)}/notes`, { notes }),

  // Picking actions
  scan: (sessionId, barcode, operatorId, focusSku = null) =>
    req('POST', `/sessions/${sessionId}/scan`, { barcode, operator_id: operatorId, focus_sku: focusSku }),
  scanBox: (sessionId, barcode, operatorId, focusSku = null) =>
    req('POST', `/sessions/${sessionId}/scan-box`, { barcode, operator_id: operatorId, focus_sku: focusSku }),
  undo: (sessionId, sku, operatorId) =>
    req('POST', `/sessions/${sessionId}/undo`, { sku, operator_id: operatorId }),
  shortage: (sessionId, sku, qtyFound, operatorId, notes = null) =>
    req('POST', `/sessions/${sessionId}/shortage`, { sku, qty_found: qtyFound, operator_id: operatorId, notes }),
  outOfStock: (sessionId, sku, operatorId, notes = null) =>
    req('POST', `/sessions/${sessionId}/out-of-stock`, { sku, operator_id: operatorId, notes }),
  reopen: (sessionId, sku, operatorId) =>
    req('POST', `/sessions/${sessionId}/reopen`, { sku, operator_id: operatorId }),
  resetItem: (sessionId, sku, operatorId) =>
    req('POST', `/sessions/${sessionId}/reset-item`, { sku, operator_id: operatorId }),
  forceCompleteItem: (sessionId, sku, operatorId) =>
    req('POST', `/sessions/${sessionId}/force-complete`, { sku, operator_id: operatorId }),
  resetAllItems: (sessionId, operatorId) =>
    req('POST', `/sessions/${sessionId}/reset-all-items`, { operator_id: operatorId }),
  addBarcode: (sessionId, barcode, sku, operatorId) =>
    req('POST', `/sessions/${sessionId}/add-barcode`, { barcode, sku, operator_id: operatorId }),

  // Labels
  printLabels: (sessionId, sku, printerId) =>
    req('POST', '/labels/print', { session_id: sessionId, sku, printer_id: printerId }),
  getZpl: (sessionId, sku) =>
    req('GET', `/labels/zpl?session_id=${sessionId}&sku=${encodeURIComponent(sku)}`),
  markPrinted: (sessionId, sku) =>
    req('POST', '/labels/mark-printed', { session_id: sessionId, sku }),

  // Printers
  getPrinters: () => req('GET', '/printers/'),
  createPrinter: (name, ip_address, port) => req('POST', '/printers/', { name, ip_address, port }),

  // Barcodes
  importBarcodesExcel: (formData) => req('POST', '/barcodes/import-excel', formData, true),
  resolveBarcode: (barcode) => req('GET', `/barcodes/resolve?barcode=${encodeURIComponent(barcode)}`),
  listBarcodes: (search = '') => req('GET', `/barcodes/?search=${encodeURIComponent(search)}&limit=2000`),

  // Zebra Agent Status (via backend — funciona em HTTPS/produção)
  getZebraAgentStatus: () => req('GET', '/zebra/agent-status'),

  // Print Jobs (fila de impressão via backend — funciona em PRD)
  createPrintJob: (sessionId, sku, zplContent, operatorId) =>
    req('POST', '/print-jobs', { session_id: sessionId, sku, zpl_content: zplContent, operator_id: operatorId }),
  getPrintJobStatus: (sessionId, sku) =>
    req('GET', `/print-jobs?session_id=${sessionId}&sku=${encodeURIComponent(sku)}`),
  getLabelsZpl: (sessionId, sku) => 
    req('GET', `/labels/zpl?session_id=${sessionId}&sku=${encodeURIComponent(sku)}`),

  // Master Data CRUD
  createProduct: (sku, description, barcodes) =>
    req('POST', '/barcodes/product', { sku, description, barcodes }),
  updateProduct: (sku, description) =>
    req('PUT', `/barcodes/${encodeURIComponent(sku)}`, { description }),
  deleteProduct: (sku) =>
    req('DELETE', `/barcodes/${encodeURIComponent(sku)}`),
  addBarcodeToProduct: (sku, barcode) =>
    req('POST', `/barcodes/${encodeURIComponent(sku)}/barcode`, { barcode }),
  removeBarcodeFromProduct: (sku, barcode) =>
    req('DELETE', `/barcodes/${encodeURIComponent(sku)}/barcode/${encodeURIComponent(barcode)}`),

  // Stats
  getOperatorRanking: (batchId = null, marketplace = null) => {
    let url = '/stats/ranking';
    const params = [];
    if (batchId) params.push(`batch_id=${batchId}`);
    if (marketplace) params.push(`marketplace=${marketplace}`);
    if (params.length > 0) url += `?${params.join('&')}`;
    return req('GET', url);
  },
  getBatchesForRanking: () => req('GET', '/stats/batches-for-ranking'),

  // Tiny ERP
  listTinyPedidos: (token = null, pagina = 1, status = null, data_inicial = null, data_final = null, force_refresh = false) => {
    let url = `/tiny/pedidos?pagina=${pagina}`;
    if (token) url += `&token=${encodeURIComponent(token)}`;
    if (status) url += `&status=${encodeURIComponent(status)}`;
    if (data_inicial) url += `&data_inicial=${encodeURIComponent(data_inicial)}`;
    if (data_final) url += `&data_final=${encodeURIComponent(data_final)}`;
    if (force_refresh) url += `&force_refresh=true`;
    return req('GET', url);
  },
  getTinyPedido: (pedidoId, token = null) => {
    let url = `/tiny/pedidos/${pedidoId}`;
    if (token) url += `?token=${encodeURIComponent(token)}`;
    return req('GET', url);
  },
  triggerTinyFullSync: (lookbackDays = 60) =>
    req('POST', `/tiny/sync/full?lookback_days=${encodeURIComponent(lookbackDays)}`),
  triggerTinyIncrementalSync: (lookbackDays = 3) =>
    req('POST', `/tiny/sync/incremental?lookback_days=${encodeURIComponent(lookbackDays)}`),
  triggerTinyReconcileSync: (lookbackDays = 30) =>
    req('POST', `/tiny/sync/reconcile?lookback_days=${encodeURIComponent(lookbackDays)}`),
  getTinySyncStatus: () => req('GET', '/tiny/sync/status'),
  getTinySeparacoes: (pagina = 1, data_inicial = null, data_final = null) => {
    let url = `/tiny/separacoes?pagina=${pagina}`;
    if (data_inicial) url += `&data_inicial=${encodeURIComponent(data_inicial)}`;
    if (data_final) url += `&data_final=${encodeURIComponent(data_final)}`;
    return req('GET', url);
  },
  
  // Tiny Picking Lists (Consolidação)
  warmSeparationCache: (separationIds) => req('POST', '/tiny/separation-cache/warm', { separation_ids: separationIds }),
  getSeparationStatuses: () => req('GET', '/tiny/separation-statuses'),
  revertSeparationStatuses: (separationIds) => req('POST', '/tiny/separation-statuses/revert', { separation_ids: separationIds }),
  createPickingList: (name, separationIds) => req('POST', '/tiny/picking-lists', { name, separation_ids: separationIds }),
  getPickingLists: () => req('GET', '/tiny/picking-lists'),
  getPickingListDetails: (listId) => req('GET', `/tiny/picking-lists/${listId}`),
  
  // New Tiny Picking Actions
  resolveBarcode: (code) => req('GET', `/tiny/resolve-barcode/${encodeURIComponent(code)}`),
  linkBarcode: (barcode, sku) => req('POST', '/tiny/link-barcode', { barcode, sku }),
  pickItem: (itemId, body = {}) => req('POST', `/tiny/picking-items/${itemId}/pick`, body),
  unpickItem: (itemId) => req('POST', `/tiny/picking-items/${itemId}/unpick`, {}),
  clearShortage: (itemId) => req('POST', `/tiny/picking-items/${itemId}/clear-shortage`, {}),
  
  // Diagnóstico: envia log do frontend para o backend
  sendLog: (level, message, context = {}) => {
    req('POST', '/admin/frontend-log', { level, message, context }).catch(() => {})
  },

  // Relatório de Faltas (v2)
  reportShortage: (data) => req('POST', '/tiny/report-shortage', data),
  getShortages: () => req('GET', '/tiny/shortages'),
  
  // App Health & Gemma AI Control Panel
  getHealth: () => req('GET', '/health'),
  chatWithGemma: (messages) => req('POST', '/v2/ai/chat', { messages }),
  
  // Generic Helpers
  get: (path) => req('GET', path),
  post: (path, body) => req('POST', path, body)
}
