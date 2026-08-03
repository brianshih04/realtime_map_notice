<script setup>
import { ref, computed, onMounted } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// ==========================================
// 地圖核心與地址狀態
// ==========================================
const map = ref(null)
const currentCoords = ref({ lat: 25.0478, lng: 121.5170 })
const locationText = ref('正在取得真實 GPS 座標...')
const eventsList = ref([])
const markerMap = ref(new Map())

const fetchAddress = async (lat, lng) => {
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

const createColoredPin = (category) => {
  const colorMap = { info: '#34c759', warning: '#ffcc00', danger: '#ff3b30' }
  return L.divIcon({
    className: 'custom-pin-container',
    html: `<div class="pin-body" style="background-color: ${colorMap[category] || '#ff7f50'};"></div>`,
    iconSize: [28, 28], iconAnchor: [14, 28], popupAnchor: [0, -24]
  })
}

// 輔助函式：將上傳的 File 轉換為 Base64 字串
const convertFileToBase64 = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.readAsDataURL(file)
    reader.onload = () => resolve(reader.result)
    reader.onerror = (error) => reject(error)
  })
}

// 取得或自動產生匿名的 User ID (保存在瀏覽器 localStorage)
const getOrCreateUserId = () => {
  let userId = localStorage.getItem('app_user_id')
  if (!userId) {
    userId = 'user_' + Math.random().toString(36).substring(2, 9)
    localStorage.setItem('app_user_id', userId)
  }
  return userId
}

// ==========================================
// WebSocket 即時推播串接 (Port 8003)
// ==========================================
const wsStatus = ref('connecting') // 可選：記錄連線狀態

const setupWebSocket = () => {
  const userId = getOrCreateUserId()
  // 建立連線，帶入動態 userId
  const ws = new WebSocket(`ws://127.0.0.1:8003/ws/${userId}`)

  ws.onopen = () => {
    console.log('✅ WebSocket 即時廣播頻道連線成功！')
    wsStatus.value = 'connected'
  }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      console.log('📩 收到 WebSocket 推播訊息：', data)

      // 1. 過慮掉握手訊息 {"type":"hello", "message":"Hello"}
      if (data.type === 'hello') return

      // 2. 如果收到的是新事件廣播 (例如 event_created / new_event)
      // 解析資料並自動在地圖與列表上繪製圖釘
      const eventData = data.event || data.payload || data

      if (eventData.latitude && eventData.longitude) {
        const eventLat = eventData.latitude
        const eventLng = eventData.longitude
        const dist = getDistance(currentCoords.value.lat, currentCoords.value.lng, eventLat, eventLng)
        const walkTime = Math.max(1, Math.round(dist / 80))

        const newEvent = {
          id: eventData.event_id || eventData.id || Date.now(),
          title: eventData.title || '即時新通知',
          category: eventData.severity === 'urgent' ? 'danger' : (eventData.severity || 'info'),
          description: eventData.message || eventData.description || '周遭有新動態發布',
          location: { lat: eventLat, lng: eventLng },
          distance: dist,
          walkTime: walkTime,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }

        // 避免重複推入相同 ID 的事件
        if (!markerMap.value.has(newEvent.id)) {
          eventsList.value.unshift(newEvent)

          const marker = L.marker([newEvent.location.lat, newEvent.location.lng], {
            icon: createColoredPin(newEvent.category)
          })
          const categoryLabels = { info: '🟢 空位/活動', warning: '🟡 遺失/擁擠', danger: '🔴 緊急突發' }
          const popupContent = `
            <div style="font-family: sans-serif; min-width: 180px;">
              <span style="font-size: 0.75rem; color: #666; font-weight: bold;">${categoryLabels[newEvent.category]}</span>
              <h4 style="margin: 4px 0 8px 0; font-size: 1rem; color: #222;">${newEvent.title}</h4>
              <p style="margin: 0 0 8px 0; font-size: 0.85rem; color: #444;">${newEvent.description}</p>
              <div style="background: #f5f5f5; padding: 6px 8px; border-radius: 6px; font-size: 0.8rem; color: #333;">
                🚶 距離約 <b>${newEvent.distance}m</b>｜步行約 <b>${newEvent.walkTime} 分鐘</b>
              </div>
            </div>
          `
          marker.bindPopup(popupContent)

          if (selectedFilters.value[newEvent.category]) {
            marker.addTo(map.value)
          }

          markerMap.value.set(newEvent.id, marker)
          triggerToast(`🔔 收到周遭即時通報：「${newEvent.title}」`)
        }
      }
    } catch (err) {
      console.log('收到非 JSON 的純文字訊息：', event.data)
    }
  }

  ws.onerror = (error) => {
    console.error('❌ WebSocket 連線異常:', error)
    wsStatus.value = 'error'
  }

  ws.onclose = () => {
    console.warn('🔌 WebSocket 連線已中斷，5 秒後嘗試重連...')
    wsStatus.value = 'disconnected'
    // 自動重連機制
    setTimeout(() => {
      setupWebSocket()
    }, 5000)
  }
}

onMounted(() => {
  map.value = L.map('map').setView([currentCoords.value.lat, currentCoords.value.lng], 16)
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap' }).addTo(map.value)

  // 啟動 WebSocket 即時廣播頻道
  setupWebSocket()

  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const { latitude, longitude } = position.coords
        currentCoords.value = { lat: latitude, lng: longitude }
        map.value.flyTo([latitude, longitude], 17)
        fetchAddress(latitude, longitude)
        
        await fetchNearbyEvents(currentCoords.value.lat, currentCoords.value.lng);
        L.circleMarker([latitude, longitude], {
          radius: 8, fillColor: '#007aff', color: '#ffffff', weight: 2, opacity: 1, fillOpacity: 1
        }).addTo(map.value).bindPopup('<b>📍 您的真實位置</b>')
      },
      (error) => locationText.value = '無法取得定位 (使用預設座標)'
    )
  }
})

// ==========================================
// 回到自身定位 (Recenter) 邏輯
// ==========================================
const recenterMap = () => {
  if (map.value && currentCoords.value) {
    map.value.flyTo([currentCoords.value.lat, currentCoords.value.lng], 17, {
      animate: true,
      duration: 1.2
    })
  }
  
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords
        currentCoords.value = { lat: latitude, lng: longitude }
        fetchAddress(latitude, longitude)
      },
      (error) => console.warn('更新 GPS 座標失敗，維持原已知座標', error)
    )
  }
}

// ==========================================
// 過濾器與列表抽屜邏輯
// ==========================================
const selectedFilters = ref({ info: true, warning: true, danger: true })

const toggleFilter = (cat) => {
  selectedFilters.value[cat] = !selectedFilters.value[cat]
  eventsList.value.forEach(item => {
    const marker = markerMap.value.get(item.id)
    if (marker) {
      if (selectedFilters.value[item.category]) {
        if (!map.value.hasLayer(marker)) map.value.addLayer(marker)
      } else {
        if (map.value.hasLayer(marker)) map.value.removeLayer(marker)
      }
    }
  })
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

// ==========================================
// 表單與 Toast 通知狀態
// ==========================================
const showModal = ref(false)
const toastMessage = ref('')
const showToast = ref(false)
const formData = ref({ title: '', category: 'info', duration: '60', description: '', imageFile: null, imagePreview: '' })

const handleImageUpload = (e) => {
  const file = e.target.files[0]
  if (file) { formData.value.imageFile = file; formData.value.imagePreview = URL.createObjectURL(file) }
}
const removeImage = () => { formData.value.imageFile = null; formData.value.imagePreview = '' }
const triggerToast = (msg) => { toastMessage.value = msg; showToast.value = true; setTimeout(() => { showToast.value = false }, 3500) }

const handleSubmit = async () => {
  // 1. 準備送給 8002 Event Service 的 API 封包
  const apiPayload = {
    title: formData.value.title,
    message: formData.value.description || '無詳細描述',
    latitude: currentCoords.value.lat,
    longitude: currentCoords.value.lng,
    severity: formData.value.category === 'danger' ? 'urgent' : formData.value.category,
    radius_meters: 500
  }

  try {
    const response = await fetch('http://localhost:8002/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(apiPayload)
    })

    if (response.ok) {
      // 2. 後端 8002 接收成功後，前端同步即時繪製 (Optimistic UI Update)
      const dist = getDistance(currentCoords.value.lat, currentCoords.value.lng, currentCoords.value.lat, currentCoords.value.lng)
      const walkTime = Math.max(1, Math.round(dist / 80))
      
      const newEvent = {
        id: Date.now(),
        title: formData.value.title,
        category: formData.value.category,
        description: formData.value.description || '無詳細描述',
        location: { ...currentCoords.value },
        distance: dist,
        walkTime: walkTime,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
      
      // 3. 推入左下角清單
      eventsList.value.unshift(newEvent)
      
      // 4. 即時繪製 Leaflet 地圖圖釘與 popup
      const marker = L.marker([newEvent.location.lat, newEvent.location.lng], { icon: createColoredPin(newEvent.category) })
      const categoryLabels = { info: '🟢 空位/活動', warning: '🟡 遺失/擁擠', danger: '🔴 緊急突發' }
      const popupContent = `
        <div style="font-family: sans-serif; min-width: 180px;">
          <span style="font-size: 0.75rem; color: #666; font-weight: bold;">${categoryLabels[newEvent.category]}</span>
          <h4 style="margin: 4px 0 8px 0; font-size: 1rem; color: #222;">${newEvent.title}</h4>
          <p style="margin: 0 0 8px 0; font-size: 0.85rem; color: #444;">${newEvent.description}</p>
          <div style="background: #f5f5f5; padding: 6px 8px; border-radius: 6px; font-size: 0.8rem; color: #333;">
            🚶 距離約 <b>${newEvent.distance}m</b>｜步行約 <b>${newEvent.walkTime} 分鐘</b>
          </div>
        </div>
      `
      marker.bindPopup(popupContent)
      
      if (selectedFilters.value[newEvent.category]) {
        marker.addTo(map.value).openPopup()
      }
      
      markerMap.value.set(newEvent.id, marker)

      // 5. 關閉 Modal、跳出 Toast 並重置表單
      showModal.value = false
      triggerToast(`成功發布「${newEvent.title}」！已同步新增至地圖與清單。`)
      formData.value = { title: '', category: 'info', duration: '60', description: '', imageFile: null, imagePreview: '' }
    } else {
      triggerToast('發布失敗，請確認 API 欄位格式！')
    }
    
  } catch (error) {
    console.error('網路連線失敗:', error)
    triggerToast('網路請求失敗，請確認是否已啟動 Docker 本機環境！')
  }
}

// 取得周遭事件 (GET API)
const fetchNearbyEvents = async (lat, lng) => {
  try {
    const response = await fetch(`http://localhost:8001/locations/nearby?latitude=${lat}&longitude=${lng}&radius=3000`);
    if (response.ok) {
      const data = await response.json();
      
      // 清空舊圖釘與清單
      markerMap.value.forEach(marker => marker.remove());
      markerMap.value.clear();
      eventsList.value = [];

      const rawEvents = Array.isArray(data) ? data : (data.events || data.locations || []);

      rawEvents.forEach(event => {
        if (typeof event === 'string') return;

        const eventLat = event.latitude || lat;
        const eventLng = event.longitude || lng;
        const dist = getDistance(lat, lng, eventLat, eventLng);
        const walkTime = Math.max(1, Math.round(dist / 80));
        
        const newEvent = {
          id: event.event_id || event.id || Date.now(),
          title: event.title || '周遭動態',
          category: event.severity === 'urgent' ? 'danger' : (event.severity || 'info'), 
          description: event.message || event.description || '附近有動態發布',
          location: { lat: eventLat, lng: eventLng },
          distance: dist,
          walkTime: walkTime,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        
        eventsList.value.push(newEvent);
        
        const marker = L.marker([newEvent.location.lat, newEvent.location.lng], { icon: createColoredPin(newEvent.category) });
        const categoryLabels = { info: '🟢 空位/活動', warning: '🟡 遺失/擁擠', danger: '🔴 緊急突發' };
        const popupContent = `
          <div style="font-family: sans-serif; min-width: 180px;">
            <span style="font-size: 0.75rem; color: #666; font-weight: bold;">${categoryLabels[newEvent.category]}</span>
            <h4 style="margin: 4px 0 8px 0; font-size: 1rem; color: #222;">${newEvent.title}</h4>
            <p style="margin: 0 0 8px 0; font-size: 0.85rem; color: #444;">${newEvent.description}</p>
            <div style="background: #f5f5f5; padding: 6px 8px; border-radius: 6px; font-size: 0.8rem; color: #333;">
              🚶 距離約 <b>${newEvent.distance}m</b>｜步行約 <b>${newEvent.walkTime} 分鐘</b>
            </div>
          </div>
        `;
        marker.bindPopup(popupContent);
        
        if (selectedFilters.value[newEvent.category]) {
          marker.addTo(map.value);
        }
        
        markerMap.value.set(newEvent.id, marker);
      });
    }
  } catch (error) {
    console.error('拉取事件時發生網路錯誤:', error);
  }
};
</script>

<template>
  <div class="app-container">
    <!-- 頂部純淨搜尋列 -->
    <header class="top-nav">
      <div class="search-bar">
        <span class="search-icon">
          <svg viewBox="0 0 24 24" width="18" height="18" stroke="#888888" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
        </span>
        <input type="text" placeholder="尋找事件或地點..." />
      </div>
    </header>

    <!-- Toast 通知 -->
    <transition name="toast">
      <div v-if="showToast" class="toast-card">
        <span class="toast-icon">✨</span><span class="toast-text">{{ toastMessage }}</span>
      </div>
    </transition>

    <!-- 地圖容器 -->
    <div id="map"></div>

    <!-- 左下角：「📋 查看附近清單」按鈕 -->
    <button class="list-fab-btn" @click="showListModal = true">
      📋 列表 <span v-if="filteredSortedEvents.length > 0" class="badge">{{ filteredSortedEvents.length }}</span>
    </button>

    <!-- 右下方「定位回正」按鈕 -->
    <button class="recenter-btn" @click="recenterMap" title="回到我的位置">
      <svg viewBox="0 0 24 24" width="20" height="20" stroke="#555555" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="8"></circle>
        <line x1="12" y1="2" x2="12" y2="4"></line>
        <line x1="12" y1="20" x2="12" y2="22"></line>
        <line x1="2" y1="12" x2="4" y2="12"></line>
        <line x1="20" y1="12" x2="22" y2="12"></line>
      </svg>
    </button>

    <!-- 右下角懸浮按鈕 FAB -->
    <button class="fab-btn" @click="showModal = true">＋</button>

    <!-- 周遭事件清單抽屜 -->
    <div v-if="showListModal" class="modal-overlay" @click.self="showListModal = false">
      <div class="modal-card list-card-container">
        <header class="modal-header">
          <button class="close-btn" @click="showListModal = false">⊗</button>
          <h3>附近事件清單 (由近到遠)</h3>
          <div style="width: 24px;"></div>
        </header>

        <div class="list-filter-bar">
          <button type="button" :class="['chip chip-green', { active: selectedFilters.info }]" @click="toggleFilter('info')">
            🟢 空位/活動
          </button>
          <button type="button" :class="['chip chip-yellow', { active: selectedFilters.warning }]" @click="toggleFilter('warning')">
            🟡 遺失/擁擠
          </button>
          <button type="button" :class="['chip chip-red', { active: selectedFilters.danger }]" @click="toggleFilter('danger')">
            🔴 緊急突發
          </button>
        </div>

        <div v-if="filteredSortedEvents.length === 0" class="empty-state">
          目前勾選的類別中，附近暫無發布的事件。
        </div>

        <div v-else class="event-list">
          <div v-for="item in filteredSortedEvents" :key="item.id" class="event-list-item" @click="flyToEvent(item)">
            <div class="item-left"><span class="item-cat-dot" :class="`dot-${item.category === 'info' ? 'green' : item.category === 'warning' ? 'yellow' : 'red'}`"></span></div>
            <div class="item-main">
              <div class="item-title">{{ item.title }}</div>
              <div class="item-desc">{{ item.description || '無詳細描述' }}</div>
              <div class="item-time">發布時間：{{ item.timestamp }}</div>
            </div>
            <div class="item-right">
              <span class="dist-badge">🚶 {{ item.walkTime }}分</span>
              <span class="dist-meter">{{ item.distance }}m</span>
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

          <div class="form-group category-group">
            <label class="group-label">事件類別選擇：</label>
            <div class="radio-options">
              <label class="radio-item"><input type="radio" v-model="formData.category" value="info" /><span class="dot dot-green"></span><span>空位 / 活動 (綠色圖釘)</span></label>
              <label class="radio-item"><input type="radio" v-model="formData.category" value="warning" /><span class="dot dot-yellow"></span><span>遺失 / 擁擠 (黃色圖釘)</span></label>
              <label class="radio-item"><input type="radio" v-model="formData.category" value="danger" /><span class="dot dot-red"></span><span>緊急 / 突發 (紅色圖釘)</span></label>
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

          <button type="submit" class="submit-btn">確認發布</button>
        </form>
      </div>
    </div>
  </div>
</template>