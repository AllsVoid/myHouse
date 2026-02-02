<script setup>
import { computed, onMounted, reactive, ref, nextTick } from 'vue'

const houses = ref([])
const search = ref('')
const showForm = ref(false)
const editingId = ref(null)
const isSaving = ref(false)
const errorMessage = ref('')
const layoutImages = ref([])
const layoutImageType = ref('')
const fileInputRef = ref(null)
const showMap = ref(false)
const showImageViewer = ref(false)
const viewerImages = ref([])
const viewerIndex = ref(0)
const viewerImageTitle = ref('')
const viewerScale = ref(1)
const viewerRotate = ref(0)
const viewerContainerRef = ref(null)
let touchStartX = 0
let touchStartY = 0
let touchStartDistance = 0
let touchStartScale = 1
let isPinching = false
const mapLoading = ref(false)
const mapError = ref('')
const mapRef = ref(null)
const mapInstance = ref(null)
const mapMarkers = ref([])
const mapInfoWindow = ref(null)
const mapCache = ref({ etag: '', lastModified: '', data: null })
const amapKey = ref('')
const amapSecurity = ref('')

const form = reactive({
  name: '',
  address: '',
  area: '',
  price: '',
  layout: '',
  building: '',
  floor: '',
  elevator: '',
  age: '',
  ownership: '',
  usage: '',
  houseStatus: '',
  intention: '',
  houseCode: '',
  link: '',
  note: ''
})

const filteredHouses = computed(() => {
  const keyword = search.value.trim().toLowerCase()
  return houses.value.filter((item) => {
    if (!keyword) return true
    const text = `${item.name} ${item.address}`.toLowerCase()
    return text.includes(keyword)
  })
})

async function loadFromApi() {
  errorMessage.value = ''
  try {
    const resp = await fetch('/api/houses')
    if (!resp.ok) throw new Error('读取房屋数据失败')
    houses.value = await resp.json()
  } catch (err) {
    errorMessage.value = err.message || '读取房屋数据失败'
    houses.value = []
  }
}

function resetForm() {
  editingId.value = null
  form.name = ''
  form.address = ''
  form.area = ''
  form.price = ''
  form.layout = ''
  form.building = ''
  form.floor = ''
  form.elevator = ''
  form.age = ''
  form.ownership = ''
  form.usage = ''
  form.houseStatus = ''
  form.intention = ''
  form.houseCode = ''
  form.link = ''
  form.note = ''
  layoutImages.value = []
  layoutImageType.value = ''
}

function openCreate() {
  resetForm()
  showForm.value = true
}

function openEdit(item) {
  editingId.value = item.id
  form.name = item.name
  form.address = item.address
  form.area = item.area ?? ''
  form.price = item.price ?? ''
  form.layout = item.layout || ''
  form.building = item.building || ''
  form.floor = item.floor || ''
  form.elevator = item.elevator || ''
  form.age = item.age || ''
  form.ownership = item.ownership || ''
  form.usage = item.usage || ''
  form.houseStatus = item.houseStatus || ''
  form.intention = item.intention || ''
  form.houseCode = item.houseCode || ''
  form.link = item.link || ''
  layoutImages.value = item.layoutImages?.length
    ? [...item.layoutImages]
    : item.layoutImageData
      ? [item.layoutImageData]
      : []
  layoutImageType.value = item.layoutImageType || ''
  form.note = item.note || ''
  showForm.value = true
}

function closeForm() {
  showForm.value = false
  resetForm()
}

async function submitForm() {
  if (
    !form.name.trim()
    || !form.address.trim()
    || !String(form.area).trim()
    || !String(form.price).trim()
  ) return
  const payload = {
    name: form.name.trim(),
    address: form.address.trim(),
    area: form.area,
    price: form.price,
    layout: form.layout.trim(),
    building: form.building.trim(),
    floor: form.floor.trim(),
    elevator: form.elevator.trim(),
    age: form.age.trim(),
    ownership: form.ownership.trim(),
    usage: form.usage.trim(),
    houseStatus: form.houseStatus.trim(),
    intention: form.intention.trim(),
    houseCode: form.houseCode.trim(),
    link: form.link.trim(),
    layoutImages: layoutImages.value,
    layoutImageData: layoutImages.value[0] || '',
    layoutImageType: layoutImageType.value,
    note: form.note.trim()
  }
  isSaving.value = true
  errorMessage.value = ''
  try {
    if (editingId.value) {
      const resp = await fetch(`/api/houses/${editingId.value}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      if (!resp.ok) throw new Error('更新失败')
      const updated = await resp.json()
      houses.value = houses.value.map((item) =>
        item.id === editingId.value ? updated : item
      )
    } else {
      const resp = await fetch('/api/houses', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      if (!resp.ok) throw new Error('保存失败')
      const created = await resp.json()
      houses.value.unshift(created)
    }
    await refreshMapCache()
    closeForm()
  } catch (err) {
    errorMessage.value = err.message || '保存失败'
  } finally {
    isSaving.value = false
  }
}

async function deleteHouse(item) {
  if (!window.confirm(`确认删除 ${item.name} 吗？`)) return
  try {
    const resp = await fetch(`/api/houses/${item.id}`, { method: 'DELETE' })
    if (!resp.ok) throw new Error('删除失败')
    houses.value = houses.value.filter((h) => h.id !== item.id)
    await refreshMapCache()
  } catch (err) {
    errorMessage.value = err.message || '删除失败'
  }
}

function formatArea(value) {
  if (value === '' || value === null || value === undefined) return '-'
  const num = Number(value)
  return Number.isFinite(num) ? `${num.toFixed(2)} ㎡` : '-'
}

onMounted(loadFromApi)

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[data-src="${src}"]`)
    if (existing) {
      if (existing.getAttribute('data-loaded') === 'true') resolve()
      existing.addEventListener('load', () => resolve())
      return
    }
    const script = document.createElement('script')
    script.src = src
    script.async = true
    script.setAttribute('data-src', src)
    script.onload = () => {
      script.setAttribute('data-loaded', 'true')
      resolve()
    }
    script.onerror = () => reject(new Error(`脚本加载失败: ${src}`))
    document.head.appendChild(script)
  })
}

async function ensureAmapLoaded() {
  const resp = await fetch('/api/config')
  if (!resp.ok) throw new Error('获取地图配置失败')
  const config = await resp.json()
  amapKey.value = config.amap_js_key || ''
  amapSecurity.value = config.amap_security_js_code || ''
  if (!amapKey.value) throw new Error('未配置 AMAP_JS_KEY')
  if (amapSecurity.value) {
    window._AMapSecurityConfig = { securityJsCode: amapSecurity.value }
  }
  if (!window.AMap) {
    await loadScript(`https://webapi.amap.com/maps?v=2.0&key=${amapKey.value}`)
  }
}

async function fetchHouseGeoJson() {
  if (mapCache.value.data) {
    return mapCache.value.data
  }
  const resp = await fetch('/api/houses/geojson')
  if (!resp.ok) throw new Error('房源地图数据加载失败')
  const data = await resp.json()
  mapCache.value.data = data
  return data
}

function clearMapMarkers() {
  if (mapMarkers.value.length && mapInstance.value) {
    mapInstance.value.remove(mapMarkers.value)
  }
  mapMarkers.value = []
}

function formatPrice(value) {
  if (value === '' || value === null || value === undefined) return '-'
  const num = Number(value)
  return Number.isFinite(num) ? `${num.toFixed(2)} 万元` : '-'
}

function getItemImages(item) {
  if (!item) return []
  if (Array.isArray(item.layoutImages) && item.layoutImages.length) {
    return item.layoutImages
  }
  if (item.layoutImageData) {
    return [item.layoutImageData]
  }
  return []
}

function renderHousesOnMap(geojson) {
  clearMapMarkers()
  if (!geojson || geojson.type !== 'FeatureCollection') return
  const features = geojson.features || []
  if (!features.length) return
  const markers = []
  features.forEach((feature) => {
    const coords = feature?.geometry?.coordinates
    if (!coords || coords.length < 2) return
    const props = feature.properties || {}
    const marker = new AMap.Marker({
      position: coords,
      title: props.name || props.address || '房源'
    })
    marker.setExtData(props)
    marker.on('click', () => {
      const info = marker.getExtData() || {}
      const name = info.name || '房源'
      const address = info.address || ''
      const building = info.building ? `楼幢: ${info.building}` : ''
      const floor = info.floor ? `楼层: ${info.floor}` : ''
      const layout = info.layout ? `户型: ${info.layout}` : ''
      const area = info.area ? `面积: ${Number(info.area).toFixed(2)} ㎡` : ''
      const price = info.price !== null && info.price !== undefined
        ? `价格: ${Number(info.price).toFixed(2)} 万元`
        : ''
      const content = `
        <div style="font-size:13px;line-height:1.5;">
          <div style="font-weight:600;margin-bottom:4px;">${name}</div>
          <div>${address}</div>
          <div>${[building, floor, layout].filter(Boolean).join(' | ')}</div>
          <div>${[area, price].filter(Boolean).join(' | ')}</div>
        </div>
      `
      if (!mapInfoWindow.value) {
        mapInfoWindow.value = new AMap.InfoWindow({ offset: new AMap.Pixel(0, -20) })
      }
      mapInfoWindow.value.setContent(content)
      mapInfoWindow.value.open(mapInstance.value, marker.getPosition())
    })
    markers.push(marker)
  })
  mapMarkers.value = markers
  mapInstance.value.add(markers)
  mapInstance.value.setFitView(markers)
}

async function openMap() {
  showMap.value = true
  mapError.value = ''
  mapLoading.value = true
  try {
    await ensureAmapLoaded()
    await nextTick()
    if (mapRef.value) {
      if (mapInstance.value) {
        mapInstance.value.destroy()
        mapInstance.value = null
      }
      mapInstance.value = new AMap.Map(mapRef.value, {
        zoom: 12,
        center: [120.5853, 31.2989]
      })
    }
    const geojson = await fetchHouseGeoJson()
    renderHousesOnMap(geojson)
  } catch (err) {
    mapError.value = err.message || '地图加载失败'
  } finally {
    mapLoading.value = false
  }
}

function closeMap() {
  showMap.value = false
  clearMapMarkers()
  if (mapInfoWindow.value) {
    mapInfoWindow.value.close()
  }
  if (mapInstance.value) {
    mapInstance.value.destroy()
    mapInstance.value = null
  }
}

function openImageViewer(images, index, title) {
  if (!images?.length) return
  viewerImages.value = images
  viewerIndex.value = index || 0
  viewerImageTitle.value = title || '户型图'
  viewerScale.value = 1
  viewerRotate.value = 0
  showImageViewer.value = true
  nextTick(() => {
    viewerContainerRef.value?.focus()
  })
}

function closeImageViewer() {
  showImageViewer.value = false
  viewerImages.value = []
  viewerIndex.value = 0
  viewerImageTitle.value = ''
  viewerScale.value = 1
  viewerRotate.value = 0
}

function viewerPrev() {
  if (!viewerImages.value.length) return
  viewerIndex.value =
    (viewerIndex.value - 1 + viewerImages.value.length) % viewerImages.value.length
}

function viewerNext() {
  if (!viewerImages.value.length) return
  viewerIndex.value = (viewerIndex.value + 1) % viewerImages.value.length
}

function zoomIn() {
  viewerScale.value = Math.min(3, viewerScale.value + 0.2)
}

function zoomOut() {
  viewerScale.value = Math.max(0.4, viewerScale.value - 0.2)
}

function rotateLeft() {
  viewerRotate.value -= 90
}

function rotateRight() {
  viewerRotate.value += 90
}

function handleKeydown(event) {
  if (!showImageViewer.value) return
  if (event.key === 'ArrowLeft') {
    viewerPrev()
  } else if (event.key === 'ArrowRight') {
    viewerNext()
  } else if (event.key === '+' || event.key === '=') {
    zoomIn()
  } else if (event.key === '-') {
    zoomOut()
  } else if (event.key === 'Escape') {
    closeImageViewer()
  }
}

function handleWheel(event) {
  if (!showImageViewer.value) return
  if (event.deltaY < 0) {
    zoomIn()
  } else {
    zoomOut()
  }
}

function getDistance(touches) {
  const [a, b] = touches
  const dx = a.clientX - b.clientX
  const dy = a.clientY - b.clientY
  return Math.hypot(dx, dy)
}

function handleTouchStart(event) {
  if (!showImageViewer.value) return
  if (event.touches.length === 2) {
    isPinching = true
    touchStartDistance = getDistance(event.touches)
    touchStartScale = viewerScale.value
  } else if (event.touches.length === 1) {
    isPinching = false
    touchStartX = event.touches[0].clientX
    touchStartY = event.touches[0].clientY
  }
}

function handleTouchMove(event) {
  if (!showImageViewer.value) return
  if (event.touches.length === 2) {
    const distance = getDistance(event.touches)
    const scale = touchStartScale * (distance / touchStartDistance)
    viewerScale.value = Math.min(3, Math.max(0.4, scale))
  }
}

function handleTouchEnd(event) {
  if (!showImageViewer.value) return
  if (isPinching) {
    if (event.touches.length === 0) {
      isPinching = false
    }
    return
  }
  if (event.changedTouches.length !== 1) return
  const dx = event.changedTouches[0].clientX - touchStartX
  const dy = event.changedTouches[0].clientY - touchStartY
  if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) {
    if (dx > 0) {
      viewerPrev()
    } else {
      viewerNext()
    }
  }
}

async function refreshMapCache() {
  mapCache.value.data = null
  if (!showMap.value) return
  mapLoading.value = true
  mapError.value = ''
  try {
    const geojson = await fetchHouseGeoJson()
    renderHousesOnMap(geojson)
  } catch (err) {
    mapError.value = err.message || '地图加载失败'
  } finally {
    mapLoading.value = false
  }
}

function readImageFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = () => reject(new Error('读取图片失败'))
    reader.readAsDataURL(file)
  })
}

async function handleImageChange(event) {
  const files = Array.from(event.target.files || [])
  if (!files.length) return
  for (const file of files) {
    const dataUrl = await readImageFile(file)
    layoutImages.value.push(dataUrl)
    layoutImageType.value = file.type || 'image'
  }
  event.target.value = ''
}

async function handlePaste(event) {
  const items = event.clipboardData?.items || []
  const imageItem = Array.from(items).find((item) => item.type.startsWith('image/'))
  if (!imageItem) return
  const file = imageItem.getAsFile()
  if (!file) return
  const dataUrl = await readImageFile(file)
  layoutImages.value.push(dataUrl)
  layoutImageType.value = file.type || 'image'
}

function removeImage(index) {
  layoutImages.value.splice(index, 1)
}

function clearImage() {
  layoutImages.value = []
  layoutImageType.value = ''
}

function triggerFilePicker(event) {
  event.stopPropagation()
  fileInputRef.value?.click()
}
</script>

<template>
  <div class="house-page">
    <header class="house-header">
      <div>
        <h1>房屋管理</h1>
        <p>本地数据管理，浏览器内保存。</p>
      </div>
      <RouterLink class="ghost-link" to="/">返回导航</RouterLink>
    </header>

    <section class="house-toolbar">
      <input v-model="search" type="search" placeholder="搜索名称/地址" />
      <button @click="openCreate">新增房屋</button>
      <button class="ghost-link" type="button" @click="openMap">看房地图</button>
    </section>

    <div v-if="errorMessage" class="house-error">{{ errorMessage }}</div>

    <section :class="['house-form-panel', { hidden: !showForm }]">
      <h2>{{ editingId ? '编辑房屋' : '新增房屋' }}</h2>
      <form @submit.prevent="submitForm">
        <div class="form-row">
          <label>名称*</label>
          <input v-model="form.name" required />
        </div>
        <div class="form-row">
          <label>地址*</label>
          <input v-model="form.address" required />
        </div>
        <div class="form-row">
          <label>面积*</label>
          <input v-model="form.area" type="number" min="0" step="0.01" required />
        </div>
        <div class="form-row">
          <label>价格*(万元)</label>
          <input
            v-model="form.price"
            type="number"
            min="0"
            step="0.01"
            placeholder="例如：120.5"
            required
          />
        </div>
        <div class="form-row">
          <label>户型(n室m户)</label>
          <input v-model="form.layout" placeholder="例如：3室2户" />
        </div>
        <div class="form-row">
          <label>楼幢(n幢[m单元])</label>
          <input v-model="form.building" placeholder="例如：2幢3单元" />
        </div>
        <div class="form-row">
          <label>楼层</label>
          <input v-model="form.floor" placeholder="例如：12/18" />
        </div>
        <div class="form-row">
          <label>梯户(n梯m户)</label>
          <input v-model="form.elevator" placeholder="例如：2梯4户" />
        </div>
        <div class="form-row">
          <label>房屋年限</label>
          <input v-model="form.age" placeholder="例如：2016年" />
        </div>
        <div class="form-row">
          <label>交易权属</label>
          <input v-model="form.ownership" placeholder="例如：商品房" />
        </div>
        <div class="form-row">
          <label>用途</label>
          <input v-model="form.usage" placeholder="例如：住宅" />
        </div>
        <div class="form-row">
          <label>房屋状态</label>
          <select v-model="form.houseStatus">
            <option value="">请选择</option>
            <option value="待出售">待出售</option>
            <option value="已下架">已下架</option>
          </select>
        </div>
        <div class="form-row">
          <label>意向</label>
          <select v-model="form.intention">
            <option value="">请选择</option>
            <option value="待考察">待考察</option>
            <option value="不考虑">不考虑</option>
            <option value="心仪">心仪</option>
          </select>
        </div>
        <div class="form-row">
          <label>房源码</label>
          <input v-model="form.houseCode" />
        </div>
        <div class="form-row">
          <label>链接</label>
          <input v-model="form.link" type="url" placeholder="https://..." />
        </div>
        <div class="form-row">
          <label>户型图</label>
          <input
            ref="fileInputRef"
            class="file-input-hidden"
            type="file"
            accept="image/*"
            multiple
            @change="handleImageChange"
          />
          <div
            class="paste-box"
            tabindex="0"
            @paste="handlePaste"
            @click="($event) => $event.currentTarget.focus()"
          >
            <button type="button" class="plus-btn" @click="triggerFilePicker">+</button>
            <span>点击虚线区域粘贴剪切板图片 (Ctrl/Cmd + V)</span>
          </div>
          <div v-if="layoutImages.length" class="image-preview">
            <div class="image-preview-grid">
              <button
                v-for="(img, idx) in layoutImages"
                :key="img + idx"
                class="image-thumb"
                type="button"
                @click="openImageViewer(layoutImages, idx, form.name)"
              >
                <img :src="img" alt="户型图预览" />
                <span class="image-index">{{ idx + 1 }}</span>
              </button>
            </div>
            <div class="image-actions">
              <button type="button" class="ghost-link" @click="clearImage">清空图片</button>
            </div>
          </div>
        </div>
        <div class="form-row">
          <label>备注</label>
          <textarea v-model="form.note" rows="3"></textarea>
        </div>
        <div class="form-actions">
          <button type="submit" :disabled="isSaving">
            {{ isSaving ? '保存中...' : '保存' }}
          </button>
          <button type="button" class="ghost-link" @click="closeForm">取消</button>
        </div>
      </form>
    </section>

    <section class="house-list">
      <div v-if="!filteredHouses.length" class="empty-state">暂无房屋信息</div>
      <article v-for="item in filteredHouses" :key="item.id" class="house-card">
        <div class="house-card-main">
          <h3>{{ item.name }}</h3>
          <div class="house-meta">
            <span>{{ item.address }}</span>
            <span>{{ formatArea(item.area) }}</span>
            <span v-if="item.price !== null && item.price !== undefined">
              价格 {{ Number(item.price).toFixed(2) }} 万元
            </span>
            <span v-if="item.layout">{{ item.layout }}</span>
            <span v-if="item.building">{{ item.building }}</span>
            <span v-if="item.floor">{{ item.floor }}</span>
            <span v-if="item.houseStatus">状态 {{ item.houseStatus }}</span>
            <span v-if="item.intention">意向 {{ item.intention }}</span>
          </div>
          <div v-if="getItemImages(item).length" class="house-image">
            <img
              :src="getItemImages(item)[0]"
              alt="户型图"
              @click="openImageViewer(getItemImages(item), 0, item.name)"
            />
            <span class="image-count">共 {{ getItemImages(item).length }} 张</span>
          </div>
          <p class="house-note">{{ item.note || '—' }}</p>
        </div>
        <div class="house-actions">
          <button @click="openEdit(item)">编辑</button>
          <button class="danger" @click="deleteHouse(item)">删除</button>
        </div>
      </article>
    </section>

    <div v-if="showMap" class="map-modal">
      <div class="map-card">
        <header class="map-header">
          <div>
            <h2>看房地图</h2>
          </div>
          <button type="button" class="ghost-link" @click="closeMap">关闭</button>
        </header>
        <div v-if="mapError" class="map-error">{{ mapError }}</div>
        <div v-if="mapLoading" class="map-loading">地图加载中...</div>
        <div ref="mapRef" class="map-container"></div>
      </div>
    </div>

    <div v-if="showImageViewer" class="map-modal" @click.self="closeImageViewer">
      <div
        ref="viewerContainerRef"
        class="map-card image-viewer"
        tabindex="0"
        @keydown="handleKeydown"
      >
        <header class="map-header">
          <div>
            <h2>{{ viewerImageTitle }}</h2>
            <p>户型图预览</p>
          </div>
          <button type="button" class="ghost-link" @click="closeImageViewer">关闭</button>
        </header>
        <div class="image-viewer-body">
          <button class="nav-arrow left" type="button" @click="viewerPrev">‹</button>
          <img
            :src="viewerImages[viewerIndex]"
            alt="户型图大图"
            :style="{ transform: `scale(${viewerScale}) rotate(${viewerRotate}deg)` }"
            @wheel.prevent="handleWheel"
            @touchstart.passive="handleTouchStart"
            @touchmove.passive="handleTouchMove"
            @touchend.passive="handleTouchEnd"
          />
          <button class="nav-arrow right" type="button" @click="viewerNext">›</button>
          <div class="viewer-footer">
            <span>第 {{ viewerIndex + 1 }} / {{ viewerImages.length }} 张</span>
            <div class="viewer-rotate">
              <button type="button" @click="rotateLeft">⟲</button>
              <button type="button" @click="rotateRight">⟳</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
