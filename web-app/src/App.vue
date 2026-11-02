<script setup>
import { ref, shallowRef, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { AI_SERVICE_URL, EVENT_SERVICE_URL, LOCATION_SERVICE_URL, NOTIFICATION_SERVICE_URL, NOTIFICATION_WS_URL } from './config.js'
import { GOOGLE_CLIENT_ID, getSavedAuth, clearAuth, authHeaders, loginWithGoogle } from './auth.js'
import { PUSH_SUPPORTED, getPushState, enablePush, disablePush, syncPushSubscription, isStandalone } from './push.js'

// ==========================================
// 深色模式與主題切換
// ==========================================
const isDarkMode = ref(localStorage.getItem('app_theme') === 'dark')

const toggleDarkMode = () => {
  isDarkMode.value = !isDarkMode.value
  localStorage.setItem('app_theme', isDarkMode.value ? 'dark' : 'light')
}

// ==========================================
// 地圖核心與狀態
// ==========================================
const DEFAULT_COORDS = { lat: 25.0366, lng: 121.4323 } // 預設座標（輔仁大學）
const map = shallowRef(null)
const radarCircle = ref(null)
const userMarker = ref(null)
const currentCoords = ref({ ...DEFAULT_COORDS })
const locationText = ref('正在取得真實 GPS 座標...')
const eventsList = ref([])
const markerMap = ref(new Map())
const eventsRefreshing = ref(false)


// === 事件分類定義（通用版：涵蓋校園日常與街區突發） ===
const CATEGORIES = [
  {
    group: '日常動態 / 活動',
    severity: 'info',
    color: '#34c759',
    tags: ['圖書館空位', '學餐/餐廳空位', '活動/市集/擺攤', '校園/社區宣傳', '二手交流/借用']
  },
  {
    group: '生活即時 / 擁擠',
    severity: 'warning',
    color: '#ff9500',
    tags: ['失物招領', '排隊人潮長', '設施維修/故障', '交通延誤/擁塞', '空間吵鬧/違規']
  },
  {
    group: '緊急突發 / 障礙 (500m推播)',
    severity: 'danger',
    color: '#ff3b30',
    tags: ['道路/通道封閉', '車禍/交通意外', '走失動物/寵物', '天候危害/積水', '突發治安/可疑人士', '火警/瓦斯外洩']
  }
]

// 目前選中的細項標籤（預設選圖書館空位）
const selectedSubCategory = ref('圖書館空位')

// 點選標籤切換
const selectCategoryTag = (tag, severity) => {
  selectedSubCategory.value = tag
  formData.value.category = severity
}

let expirationTimer = null
let locationReportTimer = null
let eventsRefreshTimer = null
let countdownTimer = null
let lastPublishedEventId = null

const fetchAddress = async (lat, lng) => {
  // 優先走後端解析：校園內顯示大樓名（與事件標籤同一套邏輯）、校外顯示路名
  try {
    const res = await fetch(`${LOCATION_SERVICE_URL}/locations/resolve?latitude=${lat}&longitude=${lng}`)
    if (res.ok) {
      const { label } = await res.json()
      if (label) {
        locationText.value = `目前位置：${label}`
        return
      }
    }
  } catch { /* 後端解析失敗，退回 Nominatim */ }
  try {
    const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=18&addressdetails=1`)
    const data = await res.json()
    const readableName = data.address.road || data.address.building || data.address.suburb || data.display_name.split(',')[0]
    locationText.value = readableName ? `目前位置：${readableName}` : `座標：${lat.toFixed(4)}, ${lng.toFixed(4)}`
  } catch (error) {
    locationText.value = `座標：${lat.toFixed(4)}, ${lng.toFixed(4)}`
  }
}

const getDistance = (lat1, lon1, lat2, lon2) => {
  const R = 6371e3
  const dLat = (lat2 - lat1) * Math.PI / 180
  const dLon = (lon2 - lon1) * Math.PI / 180
  const a = Math.sin(dLat/2) * Math.sin(dLat/2) + Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon/2) * Math.sin(dLon/2)
  return Math.round(R * (2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a))))
}

// 使用者定位藍點圖標
const createUserPin = () => {
  return L.divIcon({
    className: 'custom-user-pin',
    html: `
      <div style="
        width: 16px;
        height: 16px;
        background-color: #007aff;
        border: 3px solid #ffffff;
        border-radius: 50%;
        box-shadow: 0 0 8px rgba(0,122,255,0.6);
      "></div>
    `,
    iconSize: [16, 16],
    iconAnchor: [8, 8]
  })
}

const createColoredPin = (category, isMine = false) => {
  const colorMap = { info: '#34c759', warning: '#ffcc00', danger: '#ff3b30' }
  const bg = colorMap[category] || '#ff3b30'
  const borderColor = isMine ? '#00d2ff' : '#ffffff'
  const borderWidth = isMine ? '3px' : '2px'

  return L.divIcon({
    className: `custom-pin-container ${isMine ? 'is-my-pin' : ''}`,
    html: `
      <div class="pin-body" style="
        background-color: ${bg};
        border: ${borderWidth} solid ${borderColor} !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
        position: relative;
        width: 100%;
        height: 100%;
        border-radius: 50% 50% 50% 0;
        transform: rotate(-45deg);
      "></div>
    `,
    iconSize: [28, 28],
    iconAnchor: [14, 28],
    popupAnchor: [0, -26]
  })
}

// ==========================================
// 登入狀態（Google 登入 → 系統 JWT）
// ==========================================
const auth = ref(getSavedAuth())
const myUser = computed(() => auth.value?.user || null)
const myUserId = computed(() => auth.value?.user?.id || '')

const getOrCreateDeviceId = () => {
  let deviceId = localStorage.getItem('rmn_device_id')
  if (!deviceId) {
    deviceId = Math.random().toString(36).slice(2, 10)
    localStorage.setItem('rmn_device_id', deviceId)
  }
  return deviceId
}
const myDeviceUid = computed(() =>
  myUserId.value ? `${myUserId.value}#${getOrCreateDeviceId()}` : ''
)

const googleBtnRef = ref(null)
const loginError = ref('')
const renderGoogleButton = () => {
  if (!window.google?.accounts?.id) {
    setTimeout(renderGoogleButton, 300)
    return
  }
  window.google.accounts.id.initialize({
    client_id: GOOGLE_CLIENT_ID,
    callback: async (response) => {
      try {
        auth.value = await loginWithGoogle(response.credential)
      } catch (err) {
        loginError.value = err?.message || '登入失敗，請再試一次'
      }
    }
  })
  window.google.accounts.id.renderButton(googleBtnRef.value, {
    theme: 'outline', size: 'large', text: 'signin_with', shape: 'pill', locale: 'zh-TW'
  })
}

const logout = () => {
  if (!confirm('確定要登出嗎？下次需重新登入才能發布事件')) return
  clearAuth()
  location.reload()
}

// ==========================================
// 綠黃紅統計長條圖計算
// ==========================================
const eventLevelCounts = computed(() => {
  let green = 0, yellow = 0, red = 0
  eventsList.value.forEach(ev => {
    // 依據 category 判斷等級（綠：空位/一般；黃：人潮/提醒；紅：突發/安全）
    if (ev.category === 'library' || ev.category === 'restaurant' || ev.category === 'facility' || ev.category === 'info') {
      green++
    } else if (ev.category === 'crowd' || ev.category === 'warning') {
      yellow++
    } else {
      red++
    }
  })
  const total = eventsList.value.length || 1
  return {
    green,
    yellow,
    red,
    greenPct: Math.round((green / total) * 100),
    yellowPct: Math.round((yellow / total) * 100),
    redPct: Math.round((red / total) * 100)
  }
})

// 過濾與發布的 Loading 動畫狀態
const isFiltering = ref(false)
const isSubmittingEvent = ref(false)

// ==========================
// 手機推播（Web Push）
// ==========================
const pushState = ref({ supported: PUSH_SUPPORTED, subscribed: false })
const showPushPrompt = ref(false)
const refreshPushState = async () => { pushState.value = await getPushState() }
refreshPushState()

if (PUSH_SUPPORTED && isStandalone() && !localStorage.getItem('push_prompt_dismissed')) {
  setTimeout(async () => {
    const st = await getPushState()
    pushState.value = st
    if (!st.subscribed) showPushPrompt.value = true
  }, 1500)
}

const onEnablePush = async () => {
  try {
    await enablePush(myDeviceUid.value)
    await refreshPushState()
    showPushPrompt.value = false
    localStorage.setItem('push_prompt_dismissed', 'enabled')
    triggerToast('🔔 通知推播已啟用')
  } catch (err) {
    triggerToast(err?.message || '推播啟用失敗')
  }
}
const onDisablePush = async () => {
  try {
    await disablePush(myDeviceUid.value)
    await refreshPushState()
    triggerToast('🔕 通知推播已關閉')
  } catch (err) {
    triggerToast(err?.message || '推播關閉失敗')
  }
}
const dismissPushPrompt = () => {
  showPushPrompt.value = false
  localStorage.setItem('push_prompt_dismissed', 'dismissed')
}

// ==========================================
// 三分頁導覽
// ==========================================
const TABS = [
  { id: 'ops', label: '事件', icon: '📊' },
  { id: 'map', label: '地圖', icon: '🗺️' },
  { id: 'mine', label: '我的', icon: '📋' },
]
const TAB_INDEX = { ops: 0, map: 1, mine: 2 }
const activeTab = ref('map')
const trackStyle = computed(() => ({
  transform: `translateX(-${TAB_INDEX[activeTab.value] * 100}vw)`
}))
const switchTab = (id) => {
  if (!TABS.some(t => t.id === id)) return
  activeTab.value = id
  if (id === 'map') {
    nextTick(() => {
      if (map.value) {
        map.value.invalidateSize()
      }
    })
  }
}

let touchStart = null
const EDGE_ZONE = 36
const onTouchStart = (e) => {
  const t = e.changedTouches[0]
  touchStart = {
    x: t.clientX,
    y: t.clientY,
    fromEdge: t.clientX < EDGE_ZONE || t.clientX > window.innerWidth - EDGE_ZONE
  }
}
const onTouchEnd = (e) => {
  if (!touchStart) return
  const t = e.changedTouches[0]
  const dx = t.clientX - touchStart.x
  const dy = t.clientY - touchStart.y
  const fromEdge = touchStart.fromEdge
  touchStart = null

  if (Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy) * 1.5) return
  if (activeTab.value === 'map' && !fromEdge) return

  const idx = TAB_INDEX[activeTab.value]
  if (dx < 0 && idx < TABS.length - 1) switchTab(TABS[idx + 1].id)
  if (dx > 0 && idx > 0) switchTab(TABS[idx - 1].id)
}

// ==========================================
// 戰情摘要頁
// ==========================================
const nowTick = ref(Date.now())
const formatCountdown = (expiresAt) => {
  const total = Math.max(0, Math.floor((expiresAt - nowTick.value) / 1000))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const sec = total % 60
  const parts = []
  if (h) parts.push(`${h} 時`)
  if (h || m) parts.push(`${m} 分`)
  parts.push(`${sec} 秒`)
  return parts.join(' ')
}

const myEvents = computed(() => eventsList.value
  .filter(e => e.userId === myUserId.value)
  .sort((a, b) => (b.createdAt || b.expiresAt) - (a.createdAt || a.expiresAt)))

const timeAgo = (createdAt) => {
  if (!createdAt) return ''
  const mins = Math.floor((Date.now() - createdAt) / 60000)
  if (mins < 1) return '剛剛'
  if (mins < 60) return `${mins} 分鐘前`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs} 小時前`
  return `${Math.floor(hrs / 24)} 天前`
}
const lifePercent = (item) => {
  if (!item.createdAt || !item.expiresAt) return 100
  const total = item.expiresAt - item.createdAt
  if (total <= 0) return 0
  return Math.max(0, Math.min(100, Math.round(((item.expiresAt - Date.now()) / total) * 100)))
}
const categoryMeta = (cat) => ({
  info:    { label: '空位/活動', color: '#34c759', icon: '🟢' },
  warning: { label: '遺失/擁擠', color: '#ff9500', icon: '🟡' },
  danger:  { label: '緊急突發', color: '#ff3b30', icon: '🔴' },
}[cat] || { label: '其他', color: '#ff7f50', icon: '📍' })

const publishFromMine = () => {
  switchTab('map')
  showModal.value = true
}
const dangerEventCount = computed(() =>
  eventsList.value.filter(e => e.category === 'danger').length)

// ==========================
// AI 事件分析與報案摘要
// ==========================
const selectedAnalysisEventId = ref('')
const analysisError = ref('')

const selectedAnalysisEvent = computed(() => {
  return eventsList.value.find(event => event.id === selectedAnalysisEventId.value) || null
})

const selectedAnalysis = computed(() => selectedAnalysisEvent.value?.analysis || null)
const analysisProviderLabel = computed(() => {
  if (!selectedAnalysis.value) return '尚未分析'
  if (selectedAnalysis.value.provider === 'llm') return 'AI 分析（LLM）'
  if (selectedAnalysis.value.provider === 'keyword-fallback') return '非 AI 分析（關鍵字 fallback）'
  if (selectedAnalysis.value.provider === 'keyword') return '非 AI 分析（關鍵字）'
  return `分析方式：${selectedAnalysis.value.provider}`
})

const selectAnalysisEvent = (eventId) => {
  selectedAnalysisEventId.value = eventId
}

const copyReportSummary = async () => {
  const summary = selectedAnalysis.value?.report_summary
  if (!summary) return

  try {
    await navigator.clipboard.writeText(summary)
    triggerToast('📋 事件摘要已複製')
  } catch {
    analysisError.value = '無法複製摘要，請確認瀏覽器權限'
  }
}

// ==========================================
// 座標上報 Location Service
// ==========================================
const reportLocation = async (lat, lng) => {
  try {
    await fetch(`${LOCATION_SERVICE_URL}/locations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: myDeviceUid.value, latitude: lat, longitude: lng })
    })
  } catch (err) {
    console.log('座標上報失敗:', err)
  }
}

// ==========================================
// 定位成功/失敗防呆處理
// ==========================================
// 500 公尺雷達圈：真實定位與預設位置（輔大）都要畫，
// 已存在時只更新圓心，避免重複圖層
const ensureRadarCircle = (latitude, longitude) => {
  if (!map.value) return
  if (!radarCircle.value) {
    radarCircle.value = L.circle([latitude, longitude], {
      radius: 500,
      color: '#007aff',
      weight: 1.5,
      fillColor: '#007aff',
      fillOpacity: 0.12,
      interactive: false
    }).addTo(map.value)
  } else {
    radarCircle.value.setLatLng([latitude, longitude])
  }
}

const handleLocationSuccess = async (position) => {
  const { latitude, longitude } = position.coords
  currentCoords.value = { lat: latitude, lng: longitude }
  fetchAddress(latitude, longitude)
  reportLocation(latitude, longitude)

  if (!map.value) return

  ensureRadarCircle(latitude, longitude)

  map.value.flyTo([latitude, longitude], 16, { animate: true, duration: 1.2 })

  if (userMarker.value) {
    userMarker.value.setLatLng([latitude, longitude])
  } else {
    userMarker.value = L.marker([latitude, longitude], { icon: createUserPin() })
      .addTo(map.value)
      .bindPopup('<b>📍 您的真實位置</b>')
  }

  await fetchNearbyEvents(latitude, longitude)
}

const handleLocationError = async (error, isManual = false) => {
  let errorMsg = '無法取得精確定位，已切換至預設位置'
  if (error && error.code) {
    switch (error.code) {
      case error.PERMISSION_DENIED:
        errorMsg = '已拒絕定位權限，使用預設位置瀏覽'
        break
      case error.POSITION_UNAVAILABLE:
        errorMsg = '定位訊號不可用，使用預設位置'
        break
      case error.TIMEOUT:
        errorMsg = '定位請求逾時，使用預設位置'
        break
    }
  }

  currentCoords.value = { ...DEFAULT_COORDS }
  locationText.value = `預設位置 (輔大校園)`
  reportLocation(DEFAULT_COORDS.lat, DEFAULT_COORDS.lng)

  if (map.value) {
    // 預設位置（輔大）同樣顯示 500 公尺推播圈，與真實定位一致
    ensureRadarCircle(DEFAULT_COORDS.lat, DEFAULT_COORDS.lng)
    if (userMarker.value) {
      userMarker.value.setLatLng([DEFAULT_COORDS.lat, DEFAULT_COORDS.lng])
    } else {
      userMarker.value = L.marker([DEFAULT_COORDS.lat, DEFAULT_COORDS.lng], { icon: createUserPin() })
        .addTo(map.value)
        .bindPopup('<b>📍 預設位置</b>')
    }
  }

  triggerToast(`⚠️ ${errorMsg}`)
  await fetchNearbyEvents(DEFAULT_COORDS.lat, DEFAULT_COORDS.lng)
}

const requestUserLocation = (isManual = false) => {
  if (!navigator.geolocation) {
    handleLocationError({ code: 0 }, isManual)
    return
  }

  navigator.geolocation.getCurrentPosition(
    (position) => {
      handleLocationSuccess(position)
      if (isManual) triggerToast('📍 已成功更新您的位置')
    },
    (error) => {
      handleLocationError(error, isManual)
    },
    { enableHighAccuracy: true, timeout: 8000, maximumAge: 10000 }
  )
}

// ==========================
// 事件過期檢查與清理邏輯
// ==========================
const checkAndCleanExpiredEvents = () => {
  const now = Date.now()
  const activeEvents = []

  eventsList.value.forEach(item => {
    if (item.expiresAt) {
      if (now >= item.expiresAt) {
        const marker = markerMap.value.get(item.id)
        if (marker && map.value) map.value.removeLayer(marker)
        markerMap.value.delete(item.id)
        return
      }
    }
    activeEvents.push(item)
  })

  eventsList.value = activeEvents
}

// ==========================
// 列表新增（統一去重入口）
// ==========================
const addEventUnique = (newEvent, { notify = true } = {}) => {
  if (!newEvent.id) return false

  const existingEvent = eventsList.value.find(event => event.id === newEvent.id)
  if (existingEvent) {
    if (newEvent.analysis) existingEvent.analysis = newEvent.analysis
    return false
  }

  if (markerMap.value.has(newEvent.id)) return false

  const isContentDuplicate = eventsList.value.some(
    e => e.title === newEvent.title && e.description === newEvent.description
  )
  if (isContentDuplicate) return false

  eventsList.value.unshift(newEvent)

  // 判斷是不是自己發布的事件（比對 myUserId 或 email）
  const isMine = !!(
  (newEvent.userId && (newEvent.userId === myUserId.value || newEvent.userId === auth.value?.user?.id)) ||
  (newEvent.user_id && (newEvent.user_id === myUserId.value || newEvent.user_id === auth.value?.user?.id)) ||
  (newEvent.user_email && newEvent.user_email === myUser.value?.email)
)

  const marker = L.marker([newEvent.location.lat, newEvent.location.lng], {
  icon: createColoredPin(newEvent.category, isMine)
  })
  marker.bindPopup(createPopupContent(newEvent))

  if (selectedFilters.value[newEvent.category]) {
    marker.addTo(map.value)
  }

  markerMap.value.set(newEvent.id, marker)

  if (notify) {
    triggerToast(`🔔 收到周遭即時通報：「${newEvent.title}」`)
  }
  return true
}

// ==========================
// WebSocket 連線與即時推播
// ==========================
const wsStatus = ref('connecting')
let mapResetUntil = 0 // 收到儀表板 reset 後的靜默期：丟棄仍在途中的事件推播
let reconnectAttempts = 0
let reconnectTimeout = null
let ws = null
let lastWsMessageAt = 0
let heartbeatWatchdog = null
let everConnected = false

const isWsAlive = () => ws && ws.readyState === WebSocket.OPEN

const resyncConnection = () => {
  if (isWsAlive()) return
  if (reconnectTimeout) clearTimeout(reconnectTimeout)
  reconnectAttempts = 0
  setupWebSocket()
}

const startHeartbeatWatchdog = () => {
  if (heartbeatWatchdog) clearInterval(heartbeatWatchdog)
  heartbeatWatchdog = setInterval(() => {
    if (isWsAlive() && Date.now() - lastWsMessageAt > 45000) {
      ws.close()
    }
  }, 10000)
}

const setupWebSocket = () => {
  if (reconnectTimeout) clearTimeout(reconnectTimeout)
  if (heartbeatWatchdog) clearInterval(heartbeatWatchdog)

  const userId = encodeURIComponent(myDeviceUid.value)
  ws = new WebSocket(`${NOTIFICATION_WS_URL}/ws/${userId}`)

  ws.onopen = () => {
    wsStatus.value = 'connected'
    reconnectAttempts = 0
    lastWsMessageAt = Date.now()
    startHeartbeatWatchdog()
    if (everConnected) fetchNearbyEvents(currentCoords.value.lat, currentCoords.value.lng)
    everConnected = true
  }

  ws.onmessage = (event) => {
    lastWsMessageAt = Date.now()
    try {
      const data = JSON.parse(event.data)
      if (data.type === 'hello') return
      if (data.type === 'ping') {
        ws.send(JSON.stringify({ type: 'pong' }))
        return
      }
      // 儀表板清空事件：立即清空本地地圖與清單，不必等 15 秒定期同步
      if (data.type === 'reset') {
        markerMap.value.forEach(marker => marker && map.value && map.value.removeLayer(marker))
        markerMap.value.clear()
        eventsList.value = []
        mapResetUntil = Date.now() + 5000 // 忽略清空瞬間還在途中的事件推播
        triggerToast('🧹 事件已由運維儀表板清空')
        return
      }
      if (Date.now() < mapResetUntil) return

      const eventData = data.event || data.payload || data

      if (eventData.latitude && eventData.longitude) {
        const eventLat = eventData.latitude
        const eventLng = eventData.longitude
        const dist = getDistance(currentCoords.value.lat, currentCoords.value.lng, eventLat, eventLng)
        const walkTime = Math.max(1, Math.round(dist / 80))
        const durationMinutes = parseFloat(eventData.duration_minutes ?? eventData.duration) || 60
        const expiresAt = eventData.expires_at ? new Date(eventData.expires_at).getTime() : (Date.now() + durationMinutes * 60 * 1000)

        if (Date.now() >= expiresAt) return

        const newEvent = {
          id: eventData.event_id || eventData.id || Date.now(),
          userId: eventData.user_id || '',
          createdAt: Date.now(),
          title: eventData.title || '即時新通知',
          category: eventData.severity === 'urgent' ? 'danger' : (eventData.severity || 'info'),
          description: eventData.message || eventData.description || '周遭有新動態發布',
          imageUrl: eventData.image_url || eventData.image || '',
          location: { lat: eventLat, lng: eventLng },
          distance: dist,
          walkTime: walkTime,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          expiresAt: expiresAt,
          analysis: eventData.analysis || null,
          locationLabel: eventData.location_label || ''
        }

        addEventUnique(newEvent, { notify: newEvent.id !== lastPublishedEventId })
      }
    } catch (err) {
      console.log('解析推播訊息失敗:', err)
    }
  }

  ws.onerror = () => { wsStatus.value = 'disconnected' }

  ws.onclose = () => {
    if (heartbeatWatchdog) clearInterval(heartbeatWatchdog)
    wsStatus.value = 'reconnecting'
    reconnectAttempts++
    const delay = Math.min(5000, 500 * Math.pow(2, reconnectAttempts))
    reconnectTimeout = setTimeout(() => { setupWebSocket() }, delay)
  }
}

const handleVisibilityResume = () => {
  if (document.visibilityState === 'visible') resyncConnection()
}
const handleNetworkOnline = () => resyncConnection()

// ==========================
// 生命週期管理
// ==========================
const onlineCount = ref(0)
let onlinePollTimer = null
const fetchOnlineCount = async () => {
  try {
    const res = await fetch(`${LOCATION_SERVICE_URL}/locations/online`)
    if (res.ok) onlineCount.value = (await res.json()).online
  } catch {}
}

const appStarted = ref(false)
const initApp = () => {
  map.value = L.map('map', {
    preferCanvas: true,
    zoomAnimation: true,
    // App 分頁以 CSS transform 滑動，transform 過的祖先容器裡
    // Leaflet 的標記縮放動畫會座標錯位（縮放時圖釘飄移、閃爍）——
    // 關閉標記動畫，並在每次縮放結束時強制圖釘重新貼回座標（見 zoomend）
    fadeAnimation: false,
    markerZoomAnimation: false
  }).setView([currentCoords.value.lat, currentCoords.value.lng], 16)

  map.value.on('zoomend', () => {
    markerMap.value.forEach((marker) => marker.update())
    if (userMarker.value) userMarker.value.update()
  })

  // 統一使用一套 OSM，深色由 CSS 濾鏡處理
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap'
  }).addTo(map.value)
  
  setupWebSocket()
  requestUserLocation()

  if (pushState.value.subscribed) {
    syncPushSubscription(myDeviceUid.value).catch(() => {})
  }

  fetchOnlineCount()
  onlinePollTimer = setInterval(fetchOnlineCount, 3000)
  expirationTimer = setInterval(checkAndCleanExpiredEvents, 10000)
  locationReportTimer = setInterval(() => {
    reportLocation(currentCoords.value.lat, currentCoords.value.lng)
  }, 30000)
  // 找到 eventsRefreshTimer 那行，改為：
  eventsRefreshTimer = setInterval(() => {
    if (activeTab.value === 'map' && map.value) {
      fetchNearbyEvents(currentCoords.value.lat, currentCoords.value.lng)
    }
  }, 15000)
  countdownTimer = setInterval(() => { nowTick.value = Date.now() }, 1000)
  document.addEventListener('visibilitychange', handleVisibilityResume)
  window.addEventListener('online', handleNetworkOnline)
}

watch(auth, async (val) => {
  if (!val || appStarted.value) return
  appStarted.value = true
  await nextTick()
  initApp()
  triggerToast(`👋 歡迎，${val.user?.name || '使用者'}！`)
})

onMounted(() => {
  if (auth.value) {
    appStarted.value = true
    initApp()
  } else {
    renderGoogleButton()
  }
})

onUnmounted(() => {
  if (expirationTimer) clearInterval(expirationTimer)
  if (locationReportTimer) clearInterval(locationReportTimer)
  if (eventsRefreshTimer) clearInterval(eventsRefreshTimer)
  if (countdownTimer) clearInterval(countdownTimer)
  if (onlinePollTimer) clearInterval(onlinePollTimer)
  if (reconnectTimeout) clearTimeout(reconnectTimeout)
  if (heartbeatWatchdog) clearInterval(heartbeatWatchdog)
  document.removeEventListener('visibilitychange', handleVisibilityResume)
  window.removeEventListener('online', handleNetworkOnline)
})

// ==========================
// 視圖與列表控制
// ==========================
const recenterMap = () => {
  if (!map.value) return
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      (position) => {
        handleLocationSuccess(position)
        map.value.flyTo([position.coords.latitude, position.coords.longitude], 16, { animate: true, duration: 1.2 })
        triggerToast('📍 已回到您的當前位置')
      },
      (error) => {
        handleLocationError(error, true)
        map.value.flyTo([currentCoords.value.lat, currentCoords.value.lng], 16)
      },
      { timeout: 5000 }
    )
  } else {
    map.value.flyTo([currentCoords.value.lat, currentCoords.value.lng], 16)
  }
}

const selectedFilters = ref({ info: true, warning: true, danger: true })

// 依目前的篩選狀態，即時顯示／隱藏地圖上所有圖釘
// （圖釘平時不會自動反應篩選變化——只在新同步、回正、發布時才會重建）
const applyFiltersToMarkers = () => {
  if (!map.value) return
  eventsList.value.forEach(item => {
    const marker = markerMap.value.get(item.id)
    if (!marker) return
    if (selectedFilters.value[item.category]) {
      if (!map.value.hasLayer(marker)) marker.addTo(map.value)
    } else if (map.value.hasLayer(marker)) {
      map.value.removeLayer(marker)
    }
  })
}

const toggleFilter = (category) => {
  // 1. 立即啟動轉圈圈
  isFiltering.value = true

  // 2. 切換分類選取狀態，並同步顯示／隱藏地圖圖釘
  selectedFilters.value[category] = !selectedFilters.value[category]
  applyFiltersToMarkers()

  // 3. 給予 350ms 的動畫回饋時間，結束後關閉轉圈
  setTimeout(() => {
    isFiltering.value = false
  }, 350)
}

const showListModal = ref(false)

const filteredSortedEvents = computed(() => {
  return eventsList.value
    .filter(item => selectedFilters.value[item.category])
    .sort((a, b) => a.distance - b.distance)
})

const flyToEvent = (item) => {
  showListModal.value = false
  map.value.flyTo([item.location.lat, item.location.lng], 18)
  const marker = markerMap.value.get(item.id)
  if (marker) {
    setTimeout(() => { marker.openPopup() }, 400)
  }
}

// ==========================
// 發布表單
// ==========================
const showModal = ref(false)
const toastMessage = ref('')
const showToast = ref(false)
const formData = ref({ title: '', category: 'info', duration: '60', description: '', imageFile: null, imagePreview: '' })

const compressImage = (file, maxSide = 1600, quality = 0.85) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('讀取照片失敗'))
    reader.onload = () => {
      const img = new Image()
      img.onerror = () => reject(new Error('照片格式無法解析'))
      img.onload = () => {
        const scale = Math.min(1, maxSide / Math.max(img.width, img.height))
        const canvas = document.createElement('canvas')
        canvas.width = Math.max(1, Math.round(img.width * scale))
        canvas.height = Math.max(1, Math.round(img.height * scale))
        const ctx = canvas.getContext('2d')
        ctx.fillStyle = '#ffffff'
        ctx.fillRect(0, 0, canvas.width, canvas.height)
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
        resolve(canvas.toDataURL('image/jpeg', quality))
      }
      img.src = reader.result
    }
    reader.readAsDataURL(file)
  })

const readFileAsDataURL = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('讀取照片失敗'))
    reader.onload = (event) => resolve(event.target.result)
    reader.readAsDataURL(file)
  })

const handleImageUpload = async (e) => {
  const file = e.target.files[0]
  if (!file) return
  try {
    if (file.size <= 200 * 1024) {
      formData.value.imageFile = file
      formData.value.imagePreview = await readFileAsDataURL(file)
      return
    }
    const compressed = await compressImage(file)
    const finalPreview = compressed.length > 2_000_000
      ? await compressImage(file, 1080, 0.7)
      : compressed
    formData.value.imageFile = file
    formData.value.imagePreview = finalPreview
  } catch (err) {
    console.error('照片處理失敗:', err)
    triggerToast(`⚠️ ${err?.message || '照片處理失敗，請換一張試試'}`)
  }
}

const removeImage = () => { 
  formData.value.imageFile = null
  formData.value.imagePreview = '' 
}

const formatApiDetail = (detail) => {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map(d => {
      const field = Array.isArray(d.loc) ? d.loc[d.loc.length - 1] : ''
      return field ? `${field}：${d.msg}` : (d.msg || JSON.stringify(d))
    }).join('；')
  }
  return JSON.stringify(detail)
}

const triggerToast = (msg) => { 
  toastMessage.value = msg
  showToast.value = true
  setTimeout(() => { showToast.value = false }, 3500) 
}

const handleSubmit = async () => {
  // 1. 防重複點擊：如果已經在送出中，直接攔截
  if (isSubmittingEvent.value) return
  isSubmittingEvent.value = true

  const durationMinutes = parseFloat(formData.value.duration) || 60
  const expiresAt = Date.now() + durationMinutes * 60 * 1000

  const finalTitle = formData.value.title.startsWith(`[${selectedSubCategory.value}]`)
    ? formData.value.title
    : `[${selectedSubCategory.value}] ${formData.value.title}`

  const apiPayload = {
    title: finalTitle,
    message: formData.value.description || '無詳細描述',
    latitude: currentCoords.value.lat,
    longitude: currentCoords.value.lng,
    severity: formData.value.category === 'danger' ? 'urgent' : formData.value.category,
    radius_meters: 500,
    duration_minutes: durationMinutes,
    image_url: formData.value.imagePreview || '',
    user_id: myUserId.value
  }

  try {
    const response = await fetch(`${EVENT_SERVICE_URL}/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(apiPayload)
    })

    if (response.ok) {
      const body = await response.json()
      lastPublishedEventId = body.event_id || null

      // 2. 先把彈窗關閉並跳出成功通知，體感速度最快！
      showModal.value = false
      triggerToast(`成功發布「${finalTitle}」！`)

      const dist = getDistance(currentCoords.value.lat, currentCoords.value.lng, currentCoords.value.lat, currentCoords.value.lng)
      const walkTime = Math.max(1, Math.round(dist / 80))

      const newEvent = {
        id: body.event_id || Date.now(),
        userId: myUserId.value,
        createdAt: Date.now(),
        title: finalTitle,
        category: formData.value.category,
        description: formData.value.description || '無詳細描述',
        imageUrl: formData.value.imagePreview || '',
        location: { ...currentCoords.value },
        distance: dist,
        walkTime: walkTime,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        expiresAt: expiresAt,
        analysis: body.analysis || null,
        locationLabel: body.location_label || ''
      }

      addEventUnique(newEvent, { notify: false })
      const marker = markerMap.value.get(newEvent.id)
      if (marker && selectedFilters.value[newEvent.category]) {
        marker.openPopup()
      }

      // 3. 背景自動同步周邊事件列表，保證清單最新
      fetchNearbyEvents(currentCoords.value.lat, currentCoords.value.lng)

      // 4. 重置表單
      formData.value = { title: '', category: 'info', duration: '60', description: '', imageFile: null, imagePreview: '' }
      selectedSubCategory.value = '圖書館空位'
    } else {
      let errorMsg = '發布失敗，請確認 API 欄位格式！'
      try {
        const err = await response.json()
        if (err && err.detail) errorMsg = `⚠️ ${formatApiDetail(err.detail)}`
      } catch (_) {}
      triggerToast(errorMsg)
    }
  } catch (error) {
    console.error('網路連線失敗:', error)
    triggerToast('網路請求失敗，請確認後端服務是否正常！')
  } finally {
    // 5. 無論成功或失敗，結束 loading 轉圈狀態
    isSubmittingEvent.value = false
  }
}

// ==========================
// 編輯 / 刪除自己的事件
// ==========================
const showEditModal = ref(false)
const editingEventId = ref(null)
const editForm = ref({ title: '', category: 'info', description: '' })
const deletingId = ref(null)

const editSelectedSubCategory = ref('')

const selectEditCategoryTag = (tag, severity) => {
  editSelectedSubCategory.value = tag
  editForm.value.category = severity
}

const startEditEvent = (item) => {
  editingEventId.value = item.id
  
  const match = (item.title || '').match(/^\[(.*?)\]\s*(.*)$/)
  if (match) {
    editSelectedSubCategory.value = match[1]
    editForm.value.title = match[2]
  } else {
    editSelectedSubCategory.value = ''
    editForm.value.title = item.title || ''
  }

  editForm.value.category = item.category
  editForm.value.description = item.description || ''
  showEditModal.value = true
}

const submitEdit = async () => {
  let finalTitle = editForm.value.title.trim()
  if (editSelectedSubCategory.value) {
    finalTitle = `[${editSelectedSubCategory.value}] ${finalTitle}`
  }

  const severity = editForm.value.category === 'danger' ? 'urgent' : editForm.value.category
  try {
    const response = await fetch(`${EVENT_SERVICE_URL}/events/${editingEventId.value}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({
        user_id: myUserId.value,
        title: finalTitle,
        message: editForm.value.description || '無詳細描述',
        severity
      })
    })

    if (response.ok) {
      const item = eventsList.value.find(e => e.id === editingEventId.value)
      if (item) {
        item.title = finalTitle
        item.description = editForm.value.description || '無詳細描述'
        item.category = editForm.value.category

        const marker = markerMap.value.get(item.id)
        if (marker) {
          // 1. 即時更換圖釘顏色
          marker.setIcon(createColoredPin(item.category, true))
          // 2. 即時更新彈跳視窗內容
          marker.bindPopup(createPopupContent(item))
        }

        // 3. 依新分類的篩選狀態，同步顯示／隱藏圖釘
        applyFiltersToMarkers()
      }
      showEditModal.value = false
      triggerToast('✅ 事件已更新')
    } else {
      let errorMsg = '更新失敗，請稍後再試！'
      try {
        const err = await response.json()
        if (err && err.detail) errorMsg = `⚠️ ${err.detail}`
      } catch (_) {}
      triggerToast(errorMsg)
    }
  } catch (error) {
    console.error('更新事件失敗:', error)
    triggerToast('網路請求失敗，請確認後端服務是否正常！')
  }
}

const deleteEvent = async (item) => {
  if (!confirm(`確定要刪除「${item.title}」嗎？`)) return
  deletingId.value = item.id
  try {
    const response = await fetch(
      `${EVENT_SERVICE_URL}/events/${item.id}?user_id=${encodeURIComponent(myUserId.value)}`,
      { method: 'DELETE', headers: authHeaders() }
    )

    if (response.ok) {
      const marker = markerMap.value.get(item.id)
      if (marker && map.value) map.value.removeLayer(marker)
      markerMap.value.delete(item.id)
      eventsList.value = eventsList.value.filter(e => e.id !== item.id)
      triggerToast('🗑️ 事件已刪除')
    } else {
      let errorMsg = '刪除失敗，請稍後再試！'
      try {
        const err = await response.json()
        if (err && err.detail) errorMsg = `⚠️ ${err.detail}`
      } catch (_) {}
      triggerToast(errorMsg)
    }
  } catch (error) {
    console.error('刪除事件失敗:', error)
    triggerToast('網路請求失敗，請確認後端服務是否正常！')
  } finally {
    deletingId.value = null
  }
}

// 取得周遭事件 (GET API)
const fetchNearbyEvents = async (lat, lng) => {
  try {
    const response = await fetch(`${EVENT_SERVICE_URL}/events?latitude=${lat}&longitude=${lng}&radius=500000`)
    if (response.ok) {
      const data = await response.json()
      markerMap.value.forEach(marker => marker.remove())
      markerMap.value.clear()
      eventsList.value = []

      const rawEvents = Array.isArray(data) ? data : (data.events || [])
      const seenIds = new Set()

      rawEvents.forEach(event => {
        if (typeof event === 'string') return

        const eventId = event.event_id || event.id
        if (!eventId || seenIds.has(eventId)) return
        seenIds.add(eventId)

        const eventLat = event.latitude || lat
        const eventLng = event.longitude || lng
        const dist = getDistance(lat, lng, eventLat, eventLng)
        const walkTime = Math.max(1, Math.round(dist / 80))

        const createdAtMs = event.created_at ? new Date(event.created_at).getTime() : Date.now()
        const durationMs = (event.duration_minutes || 60) * 60 * 1000
        const expiresAt = event.expires_at ? new Date(event.expires_at).getTime() : (createdAtMs + durationMs)

        if (Date.now() >= expiresAt) return

        const newEvent = {
          id: eventId,
          userId: event.user_id || '',
          createdAt: createdAtMs,
          title: event.title || '周遭動態',
          category: event.severity === 'urgent' ? 'danger' : (event.severity || 'info'),
          description: event.message || event.description || '附近有動態發布',
          imageUrl: event.image_url || event.image || event.imageUrl || '',
          location: { lat: eventLat, lng: eventLng },
          distance: dist,
          walkTime: walkTime,
          timestamp: new Date(createdAtMs).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          expiresAt: expiresAt,
          analysis: event.analysis || null,
          locationLabel: event.location_label || ''
        }

        const refreshNearbyEvents = async () => {
          if (eventsRefreshing.value) return
          eventsRefreshing.value = true
          try {
            await fetchNearbyEvents(currentCoords.value.lat, currentCoords.value.lng)
            triggerToast('🔄 事件列表已更新')
          } finally {
            eventsRefreshing.value = false
          }
        }

        eventsList.value.push(newEvent)

        // 同樣判斷是不是自己發布的
        const isMine = !!(
          (newEvent.userId && (newEvent.userId === myUserId.value || newEvent.userId === auth.value?.user?.id)) ||
          (newEvent.user_id && (newEvent.user_id === myUserId.value || newEvent.user_id === auth.value?.user?.id)) ||
          (newEvent.user_email && newEvent.user_email === myUser.value?.email)
        )

        const marker = L.marker([newEvent.location.lat, newEvent.location.lng], {
          icon: createColoredPin(newEvent.category, isMine)
        })
        marker.bindPopup(createPopupContent(newEvent))

        if (selectedFilters.value[newEvent.category]) {
          marker.addTo(map.value)
        }

        markerMap.value.set(newEvent.id, marker)
      })
    }
  } catch (error) {
    console.error('拉取事件時發生網路錯誤:', error)
  }
}

const createPopupContent = (item) => {
  const isMine = (item.userId && item.userId === myUserId.value) || 
                 (item.user_id && item.user_id === myUserId.value) || 
                 (item.user_email && item.user_email === myUser.value?.email)

  const categoryLabels = {
    info: '🟢 空位/活動',
    warning: '🟡 遺失/擁擠',
    danger: '🔴 緊急突發'
  }

  return `
    <div class="custom-popup ${isMine ? 'my-event-popup' : ''}">
      <div class="popup-top-row" style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
        <span class="popup-category">${categoryLabels[item.category] || '📌 事件'}</span>
        ${isMine ? '<span class="popup-my-badge">👑 我的發布</span>' : ''}
      </div>
      <div class="popup-title" style="font-weight: bold; font-size: 15px; margin-bottom: 4px; color: #1c1c1e;">
        ${item.title}
      </div>
      ${item.description && item.description !== '無詳細描述' ? `<p style="margin: 4px 0; font-size: 13px; color: #666;">${item.description}</p>` : ''}
      ${item.imageUrl ? `
      <div class="popup-photo" title="點擊查看大圖" onclick="window.openImageLightbox('${item.imageUrl}')">
        <img src="${item.imageUrl}" alt="事件照片" />
      </div>` : ''}
      <div class="popup-meta" style="font-size: 12px; color: #8e8e93; margin-top: 6px; display: flex; align-items: center; gap: 8px;">
        <span>🚶 距離約 ${item.distance || 0}m</span>
        <span>步行約 ${item.walkTime || 1} 分鐘</span>
      </div>
    </div>
  `
}

// ==========================================
// 圖片燈箱 (Lightbox)
// ==========================================
const lightboxImage = ref('')
const showLightbox = ref(false)

const openLightbox = (url) => {
  if (url) {
    lightboxImage.value = url
    showLightbox.value = true
  }
}

const closeLightbox = () => {
  showLightbox.value = false
  lightboxImage.value = ''
}

window.openImageLightbox = openLightbox
</script>

<template>
  <div v-if="auth" class="app-container" :class="{ 'dark-mode': isDarkMode }">
    <!-- 連線狀態指示膠囊 -->
    <div v-show="activeTab !== 'mine'" class="connection-pill" :class="wsStatus">
      <span class="status-indicator-dot"></span>
      <span v-if="wsStatus === 'connected'">即時同步中</span>
      <span v-else-if="wsStatus === 'reconnecting'">連線中斷，重試中...</span>
      <span v-else>伺服器未連線</span>
    </div>
    
    <!-- 即時在線人數膠囊 -->
    <div v-show="activeTab !== 'mine'" class="connection-pill online-pill">
      <span>👥 即時在線 {{ onlineCount }} 人</span>
    </div>

    <!-- Toast 通知 -->
    <transition name="toast">
      <div v-if="showToast" class="toast-card">
        <span class="toast-icon">✨</span>
        <span class="toast-text">{{ toastMessage }}</span>
      </div>
    </transition>

    <!-- 三分頁視窗：戰情摘要（左）／地圖（中）／我的發布（右） -->
    <div class="tab-viewport" @touchstart.passive="onTouchStart" @touchend.passive="onTouchEnd">
      <div class="tab-track" :style="trackStyle">

        <!-- 頁面 1：戰情摘要 -->
        <section class="tab-panel ops-panel">
          <div class="ops-header">
            <span>📊 事件摘要</span>
            <button
              type="button"
              class="refresh-events-btn"
              :disabled="eventsRefreshing"
              @click="refreshNearbyEvents"
            >
              {{ eventsRefreshing ? '整理中...' : '🔄 重新整理事件' }}
            </button>
          </div>

          <div class="stats-grid">
            <div class="stat-card">
              <span class="stat-value">{{ onlineCount }}</span>
              <span class="stat-label">線上人數</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ eventsList.length }}</span>
              <span class="stat-label">進行中事件</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ dangerEventCount }}</span>
              <span class="stat-label">緊急事件</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ myEvents.length }}</span>
              <span class="stat-label">我的發布</span>
            </div>
          </div>
          <!-- 綠黃紅事件長條圖統計 -->
          <div class="event-level-chart-card">
            <div class="chart-header">
              <span>📊 即時事件等級分佈</span>
              <span class="chart-total">共 {{ eventsList.length }} 則</span>
            </div>
  
            <div class="stacked-bar-container">
            <div class="bar-segment bar-green" :style="{ width: eventLevelCounts.greenPct + '%' }" title="生活/空位"></div>
            <div class="bar-segment bar-yellow" :style="{ width: eventLevelCounts.yellowPct + '%' }" title="人潮/提醒"></div>
               <div class="bar-segment bar-red" :style="{ width: eventLevelCounts.redPct + '%' }" title="突發/緊急"></div>
            </div>

            <div class="chart-legend">
              <div class="legend-item"><span class="dot dot-green"></span> 正常/空位: {{ eventLevelCounts.green }}</div>
              <div class="legend-item"><span class="dot dot-yellow"></span> 擁擠/注意: {{ eventLevelCounts.yellow }}</div>
            <div class="legend-item"><span class="dot dot-red"></span> 突發/緊急: {{ eventLevelCounts.red }}</div>
            </div>
          </div>
          <div class="ops-ai-card">
            <div class="ops-ai-header">
              {{ analysisProviderLabel === '尚未分析' ? '🧭 事件分析' : analysisProviderLabel }}
            </div>
            <p class="ops-ai-hint">事件發布時會自動完成分析；選擇事件即可查看結果。</p>

            <select
              v-if="eventsList.length"
              class="input-light ops-select"
              :value="selectedAnalysisEventId"
              @change="selectAnalysisEvent($event.target.value)"
            >
              <option value="">選擇事件查看分析</option>
              <option v-for="item in eventsList" :key="item.id" :value="item.id">
                {{ item.title }}
              </option>
            </select>

            <p v-else class="ops-ai-hint">目前沒有事件分析結果。</p>

            <div v-if="selectedAnalysis" class="ops-result">
              <div class="ops-result-summary">{{ selectedAnalysis.summary }}</div>

              <div class="ops-result-meta">
                類型：{{ selectedAnalysis.category }} · 建議程度：{{ selectedAnalysis.suggested_severity }}
              </div>
              <div class="ops-result-meta">
                分析方式：{{ analysisProviderLabel }}
              </div>

              <div v-if="selectedAnalysis.incident_facts?.length" class="ops-result-block">
                <div class="ops-result-title">事件經過</div>
                <ul class="ops-result-list">
                  <li v-for="fact in selectedAnalysis.incident_facts" :key="fact">{{ fact }}</li>
                </ul>
              </div>

              <div v-if="selectedAnalysis.advice?.length" class="ops-result-block">
                <div class="ops-result-title">建議處理方式</div>
                <ul class="ops-result-list">
                  <li v-for="advice in selectedAnalysis.advice" :key="advice">{{ advice }}</li>
                </ul>
              </div>

              <div v-if="selectedAnalysis.emergency_contacts?.length" class="ops-result-block">
                <div class="ops-result-title">建議聯絡</div>
                <div class="ops-contacts">
                  <span v-for="contact in selectedAnalysis.emergency_contacts" :key="contact" class="ops-contact-chip">
                    {{ contact }}
                  </span>
                </div>
              </div>

              <div v-if="selectedAnalysis.report_summary" class="ops-result-report">
                <div class="ops-result-title">事件摘要</div>
                <p>{{ selectedAnalysis.report_summary }}</p>
                <button type="button" class="copy-summary-btn" @click="copyReportSummary">
                  📋 複製事件摘要
                </button>
              </div>
            </div>
          </div>
        </section>

        <!-- 頁面 2：地圖（主畫面） -->
        <section class="tab-panel map-panel">
          <div id="map"></div>
          <!-- 地圖畫面正中央的篩選膠囊 -->
          <div v-if="isFiltering" class="map-filter-loading">
            <div class="filter-spinner"></div>
            <span>篩選中...</span>
          </div>
        </section>

        <!-- 頁面 3：我的發布 -->
        <section class="tab-panel mine-panel">
          <div class="mine-header">
            <div class="mine-header-left">
              <span class="mine-header-title">📋 我的發布</span>
              <span v-if="myEvents.length" class="mine-count">{{ myEvents.length }} 則進行中</span>
            </div>

            <!-- 右上角深淺色切換膠囊 -->
            <div
              class="theme-toggle-switch"
              :class="{ 'dark-active': isDarkMode }"
              @click="toggleDarkMode"
              :title="isDarkMode ? '目前為深色模式，點擊切換為淺色' : '目前為淺色模式，點擊切換為深色'"
            >
              <span class="switch-icon sun-icon">☀️</span>
              <span class="switch-icon moon-icon">🌙</span>
              <div class="switch-handle"></div>
            </div>
          </div>

          <!-- 登入帳號資料卡 -->
          <div v-if="myUser" class="mine-profile-card">
            <img v-if="myUser.picture" :src="myUser.picture" alt="頭像" referrerpolicy="no-referrer" class="mine-avatar" />
            <div v-else class="mine-avatar mine-avatar-placeholder">👤</div>
            <div class="mine-profile-info">
              <div class="mine-profile-name">{{ myUser.name || '已登入使用者' }}</div>
              <div class="mine-profile-email">{{ myUser.email }}</div>
            </div>
            <button type="button" class="mine-logout-btn" @click="logout">登出</button>
          </div>

          <div v-if="pushState.supported" class="mine-push-card">
            <div class="mine-push-info">
              <span class="mine-push-icon">🔔</span>
              <div>
                <div class="mine-push-title">推播通知</div>
                <div class="mine-push-status">
                  {{ pushState.subscribed ? '已啟用——緊急事件會推播到這台裝置' : '未啟用——啟用後沒開 App 也能收到事件通知' }}
                </div>
              </div>
            </div>
            <button
              type="button"
              class="mine-push-btn"
              :class="{ off: pushState.subscribed }"
              @click="pushState.subscribed ? onDisablePush() : onEnablePush()"
            >
              {{ pushState.subscribed ? '關閉' : '開啟' }}
            </button>
          </div>

          <div v-if="myEvents.length === 0" class="mine-empty">
            <div class="mine-empty-icon">📍</div>
            <div class="mine-empty-title">還沒有發布過事件</div>
            <div class="mine-empty-desc">發布的內容會出現在這裡，<br />可以隨時編輯或刪除。</div>
            <button type="button" class="mine-cta" @click="publishFromMine">＋ 發布第一則事件</button>
          </div>

          <div v-else class="mine-list">
            <div
              v-for="item in myEvents"
              :key="item.id"
              class="mine-card"
              :style="{ borderLeftColor: categoryMeta(item.category).color }"
            >
              <div class="mine-card-top">
                <span
                  class="mine-chip"
                  :style="{ backgroundColor: categoryMeta(item.category).color + '1a', color: categoryMeta(item.category).color }"
                >
                  {{ categoryMeta(item.category).icon }} {{ categoryMeta(item.category).label }}
                </span>
                <span class="mine-timeago">{{ timeAgo(item.createdAt) }}</span>
              </div>

              <div class="mine-card-title">{{ item.title }}</div>
              <p v-if="item.description && item.description !== '無詳細描述'" class="mine-card-desc">{{ item.description }}</p>

              <div class="mine-life">
                <div class="mine-life-bar">
                  <div
                    class="mine-life-fill"
                    :style="{ width: lifePercent(item) + '%', backgroundColor: categoryMeta(item.category).color }"
                  ></div>
                </div>
                <span class="mine-life-text">⏳ 剩餘 {{ formatCountdown(item.expiresAt) }}</span>
              </div>

              <div class="mine-card-footer">
                <span class="mine-meta">📍 距離 {{ item.distance }} 公尺</span>
                <span class="card-actions">
                  <button type="button" class="card-action-btn" title="編輯事件" @click="startEditEvent(item)">✏️</button>
                  <button type="button" class="card-action-btn" title="刪除事件" :disabled="deletingId === item.id" @click="deleteEvent(item)">🗑️</button>
                </span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>

    <!-- 左下角：「📋 查看附近清單」按鈕 -->
    <button v-show="activeTab === 'map'" class="list-fab-btn" @click="showListModal = true">
      📋 列表 <span v-if="filteredSortedEvents.length > 0" class="badge">{{ filteredSortedEvents.length }}</span>
    </button>

    <!-- 右下方「定位回正」按鈕 -->
    <button v-show="activeTab === 'map'" class="recenter-btn" @click="recenterMap" title="回到我的位置">
      <svg viewBox="0 0 24 24" width="20" height="20" stroke="#555555" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="8"></circle>
        <line x1="12" y1="2" x2="12" y2="4"></line>
        <line x1="12" y1="20" x2="12" y2="22"></line>
        <line x1="2" y1="12" x2="4" y2="12"></line>
        <line x1="20" y1="12" x2="22" y2="12"></line>
      </svg>
    </button>

    <!-- 右下角懸浮按鈕 FAB -->
    <button v-show="activeTab === 'map'" class="fab-btn" @click="showModal = true">＋</button>

    <!-- 底部 tab bar -->
    <nav class="tab-bar">
      <button
        v-for="t in TABS"
        :key="t.id"
        type="button"
        :class="['tab-btn', { active: activeTab === t.id }]"
        @click="switchTab(t.id)"
      >
        <span class="tab-icon">{{ t.icon }}</span>
        <span class="tab-label">{{ t.label }}</span>
      </button>
    </nav>

    <!-- 周遭事件清單抽屜 -->
    <div v-if="showListModal" class="modal-overlay" @click.self="showListModal = false">
      <div class="modal-card list-card-container">
        <header class="modal-header">
          <button class="close-btn" @click="showListModal = false">⊗</button>
          <h3>事件清單 (由近到遠)</h3>
          <div style="width: 24px;"></div>
        </header>

        <div class="list-filter-bar" style="position: relative;">
          <button type="button" :class="['chip chip-green', { active: selectedFilters.info }]" @click="toggleFilter('info')">
            🟢 空位/活動
          </button>
          <button type="button" :class="['chip chip-yellow', { active: selectedFilters.warning }]" @click="toggleFilter('warning')">
            🟡 遺失/擁擠
          </button>
          <button type="button" :class="['chip chip-red', { active: selectedFilters.danger }]" @click="toggleFilter('danger')">
            🔴 緊急突發
          </button>
          
          <!-- 過濾時出現微小旋轉圈提示 -->
          <span v-if="isFiltering" class="filter-mini-spinner" title="篩選中..."></span>
        </div>

        <div v-if="filteredSortedEvents.length === 0" class="empty-state">
          目前勾選的類別中，暫無發布的事件。
        </div>

        <div v-else class="event-list">
          <div 
            v-for="item in filteredSortedEvents" 
            :key="item.id" 
            class="event-card"
            :class="{ 'is-my-card': item.userId === myUserId }"
            @click="flyToEvent(item)"
          >
            <div 
              v-if="item.imageUrl" 
              class="card-thumb" 
              @click.stop="openLightbox(item.imageUrl)" 
              title="點擊查看大圖"
            >
              <img :src="item.imageUrl" alt="event-pic" />
            </div>

            <div class="card-content">
              <div class="card-header">
                <span class="card-title">
                  <span v-if="item.userId === myUserId" class="my-event-tag">★ 我的</span>
                  {{ item.title }}
                </span>
                <span class="card-badge" :class="item.category">
                  步行時間約 {{ item.walkTime }} 分鐘
                </span>
              </div>
              <p v-if="item.description && item.description !== '無詳細描述'" class="card-desc">{{ item.description }}</p>
              <div class="card-meta">
                <span>距離 {{ item.distance }}公尺</span>
                <span>發布時間 {{ item.timestamp }}</span>
                <span v-if="item.userId === myUserId" class="card-actions">
                  <button type="button" class="card-action-btn" title="編輯事件" @click.stop="startEditEvent(item)">✏️</button>
                  <button type="button" class="card-action-btn" title="刪除事件" :disabled="deletingId === item.id" @click.stop="deleteEvent(item)">🗑️</button>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 發布事件表單 -->
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
      <div class="modal-card">
        <header class="modal-header">
          <button class="close-btn" @click="showModal = false">⊗</button>
          <h3>發布事件</h3>
          <div style="width: 24px;"></div>
        </header>

        <form @submit.prevent="handleSubmit" class="modal-form">
          <div class="location-badge">📍 {{ locationText }}</div>
          <div class="form-group">
            <input type="text" v-model="formData.title" placeholder="請輸入事件名稱..." required class="input-light" />
          </div>

          <!-- 事件分類選擇器 -->
          <div class="category-selector-container">
            <label class="category-label">事件分類與危害程度：</label>
            <div class="category-groups">
              <div v-for="cat in CATEGORIES" :key="cat.group" class="category-group-card">
                <div class="category-group-header">
                  <span class="category-dot" :style="{ backgroundColor: cat.color }"></span>
                  <span class="category-group-title" :style="{ color: cat.color }">{{ cat.group }}</span>
                </div>
                <div class="category-tags">
                  <button
                    type="button"
                    v-for="tag in cat.tags"
                    :key="tag"
                    class="category-tag-btn"
                    :class="{ active: selectedSubCategory === tag }"
                    :style="selectedSubCategory === tag ? { borderColor: cat.color, color: cat.color, backgroundColor: cat.color + '18' } : {}"
                    @click="selectCategoryTag(tag, cat.severity)"
                  >
                    {{ tag }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div class="form-group">
            <label class="group-label">⏳ 事件時效：</label>
            <select v-model="formData.duration" class="select-light">
              <option value="30">保留 30 分鐘 (即時狀況)</option>
              <option value="60">保留 1 小時</option>
              <option value="120">保留 2 小時</option>
              <option value="1440">保留 24 小時 (全天活動)</option>
            </select>
          </div>

          <div class="form-group">
            <label class="group-label">📷 現場照片 (選填)：</label>
            <div v-if="!formData.imagePreview" class="upload-box">
              <input type="file" accept="image/*" @change="handleImageUpload" id="file-input" />
              <label for="file-input" class="upload-label">點擊上傳或拍攝照片</label>
            </div>
            <div v-else class="image-preview-container">
              <img :src="formData.imagePreview" alt="預覽圖" class="preview-img" />
              <button type="button" class="remove-img-btn" @click="removeImage">✕ 移除照片</button>
            </div>
          </div>

          <div class="form-group">
            <textarea v-model="formData.description" rows="3" placeholder="詳細描述：補充說明具體位置、特徵或狀況..." class="input-light"></textarea>
          </div>

          <!-- 原本表單最底部的送出按鈕改為： -->
<button
  type="submit"
  class="submit-btn"
  :disabled="isSubmittingEvent"
  :style="{ opacity: isSubmittingEvent ? 0.7 : 1, cursor: isSubmittingEvent ? 'not-allowed' : 'pointer' }"
>
  <span v-if="isSubmittingEvent" class="spinner-sm"></span>
  <span>{{ isSubmittingEvent ? '發布中...' : '確認發布' }}</span>
</button>
        </form>
      </div>
    </div>

    <!-- 編輯事件表單 -->
    <div v-if="showEditModal" class="modal-overlay" @click.self="showEditModal = false">
      <div class="modal-card">
        <header class="modal-header">
          <button class="close-btn" @click="showEditModal = false">⊗</button>
          <h3>編輯事件</h3>
          <div style="width: 24px;"></div>
        </header>

        <form @submit.prevent="submitEdit" class="modal-form">
          <div class="form-group">
            <input type="text" v-model="editForm.title" placeholder="事件名稱" required maxlength="100" class="input-light" />
          </div>

          <!-- 事件分類選擇器（與發布頁面一致） -->
          <div class="category-selector-container">
            <label class="category-label">事件分類與危害程度：</label>
            <div class="category-groups">
              <div v-for="cat in CATEGORIES" :key="cat.group" class="category-group-card">
                <div class="category-group-header">
                  <span class="category-dot" :style="{ backgroundColor: cat.color }"></span>
                  <span class="category-group-title" :style="{ color: cat.color }">{{ cat.group }}</span>
                </div>
                <div class="category-tags">
                  <button
                    type="button"
                    v-for="tag in cat.tags"
                    :key="tag"
                    class="category-tag-btn"
                    :class="{ active: editSelectedSubCategory === tag }"
                    :style="editSelectedSubCategory === tag ? { borderColor: cat.color, color: cat.color, backgroundColor: cat.color + '18' } : {}"
                    @click="selectEditCategoryTag(tag, cat.severity)"
                  >
                    {{ tag }}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div class="form-group">
            <textarea v-model="editForm.description" rows="3" maxlength="1000" placeholder="詳細描述..." class="input-light"></textarea>
          </div>

          <!-- 原本表單最底部的送出按鈕改為： -->
          <button
            type="submit"
            class="submit-btn"
            :disabled="isSubmittingEvent"
              :style="{ opacity: isSubmittingEvent ? 0.7 : 1, cursor: isSubmittingEvent ? 'not-allowed' : 'pointer' }"
          >
            <span v-if="isSubmittingEvent" class="spinner-sm"></span>
            <span>{{ isSubmittingEvent ? '發布中...' : '確認發布' }}</span>
          </button>
        </form>
      </div>
    </div>

    <!-- 加入主畫面後的推播詢問 -->
    <transition name="toast">
      <div v-if="showPushPrompt" class="push-prompt-overlay">
        <div class="push-prompt-card">
          <div class="push-prompt-icon">🔔</div>
          <div class="push-prompt-title">開啟通知？</div>
          <p class="push-prompt-desc">開啟後即使沒有打開 App，附近有緊急事件時也會直接推播到這台裝置。</p>
          <div class="push-prompt-actions">
            <button type="button" class="push-prompt-later" @click="dismissPushPrompt">先不用</button>
            <button type="button" class="push-prompt-enable" @click="onEnablePush">開啟通知</button>
          </div>
        </div>
      </div>
    </transition>

    <!-- 大圖燈箱 Lightbox Modal -->
    <transition name="toast">
      <div v-if="showLightbox" class="lightbox-overlay" @click="closeLightbox">
        <button class="lightbox-close-btn" @click="closeLightbox">✕</button>
        <img :src="lightboxImage" class="lightbox-img" @click.stop alt="現場大圖" />
      </div>
    </transition>
  </div>

  <!-- Google 登入頁：未登入時的唯一畫面 -->
  <div v-else class="login-screen">
    <div class="login-card">
      <div class="login-logo">📍</div>
      <h1 class="login-title">即時地圖通知</h1>
      <p class="login-subtitle">Realtime Map Notice</p>
      <p class="login-desc">登入後即可發布與接收<br />校園周遭的即時事件通知</p>
      <div ref="googleBtnRef" class="google-btn-wrap"></div>
      <div v-if="!GOOGLE_CLIENT_ID" class="login-hint">
        ⚠️ 尚未設定 VITE_GOOGLE_CLIENT_ID（見 web-app/.env.example）
      </div>
      <div v-if="loginError" class="login-error">{{ loginError }}</div>
    </div>
  </div>
</template>