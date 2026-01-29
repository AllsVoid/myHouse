<script setup>
import { onMounted, ref } from 'vue'
import '../assets/geo.css'

const errorMessage = ref('')
const apiBase = ref('')
const amapKey = ref('')
const amapSecurity = ref('')
const apiBaseEnv = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const existing = document.querySelector(`script[data-src="${src}"]`)
    if (existing) {
      existing.addEventListener('load', () => resolve())
      if (existing.getAttribute('data-loaded') === 'true') resolve()
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

onMounted(async () => {
  errorMessage.value = ''
  try {
    const configUrl = apiBaseEnv ? `${apiBaseEnv}/api/config` : '/api/config'
    const resp = await fetch(configUrl)
    if (!resp.ok) throw new Error('获取后端配置失败')
    const config = await resp.json()
    apiBase.value = (config.api_base_url || apiBaseEnv || window.location.origin).replace(/\/$/, '')
    amapKey.value = config.amap_js_key || ''
    amapSecurity.value = config.amap_security_js_code || ''
    window.__API_BASE_URL__ = apiBase.value
    window.__AMAP_KEY__ = config.amap_key || ''

    if (!amapKey.value) {
      errorMessage.value = '未配置 AMAP_JS_KEY，地图无法加载'
      return
    }
    if (amapSecurity.value) {
      window._AMapSecurityConfig = { securityJsCode: amapSecurity.value }
    }
    if (!window.AMap) {
      await loadScript(`https://webapi.amap.com/maps?v=2.0&key=${amapKey.value}`)
    }
    if (!window.__geoScriptLoaded) {
      await loadScript(`${apiBase.value}/static/app.js`)
      window.__geoScriptLoaded = true
    }
    if (!window.__geoInited && typeof window.initMap === 'function') {
      window.initMap()
      window.__geoInited = true
    }
  } catch (err) {
    errorMessage.value = err.message || '地图初始化失败'
  }
})
</script>

<template>
  <div class="geo-page">
    <header class="geo-header">
      <div>
        <h1>GeoJSON 预览器</h1>
        <p>通过 API 加载与编辑数据。</p>
      </div>
      <RouterLink class="ghost-link" to="/">返回导航</RouterLink>
    </header>
    <div v-if="errorMessage" class="geo-error">{{ errorMessage }}</div>
    <div id="controls">
      <label>选择文件：</label>
      <select id="fileSelect">
        <option value="">-- 请选择 --</option>
      </select>
      <button id="reloadBtn">重新加载当前文件</button>
      <button id="refreshListBtn">刷新文件列表</button>
      <label>校区：</label>
      <select id="schoolSelect">
        <option value="">全部</option>
      </select>
      <label>历史版本：</label>
      <select id="historySelect">
        <option value="">当前</option>
      </select>
      <button id="restoreHistoryBtn">恢复为当前</button>
      <label><input id="showPoints" type="checkbox" /> 显示点集</label>
      <label><input id="showItems" type="checkbox" /> 显示细分面</label>
      <button id="editPolygonBtn">编辑面</button>
      <button id="savePolygonBtn">保存面</button>
      <button id="editPointsBtn">编辑点</button>
      <button id="savePointsBtn">保存点</button>
      <button id="saveDbBtn">保存到数据库</button>
      <button id="resetEditsBtn">撤销编辑</button>
      <span class="status" id="status">未加载</span>

      <span class="spacer">或本地文件：</span>
      <input id="fileInput" type="file" accept=".geojson,.json" />
    </div>
    <div id="map"></div>
  </div>
</template>
