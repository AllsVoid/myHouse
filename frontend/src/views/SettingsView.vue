<script setup>
import { onMounted, reactive, ref } from 'vue'

const isLoading = ref(true)
const isSaving = ref(false)
const successMessage = ref('')
const errorMessage = ref('')
const testMessage = ref('')
const databaseUrlRef = ref(null)
const amapKeyRef = ref(null)
const amapJsKeyRef = ref(null)
const amapSecurityRef = ref(null)
const accessKeyRef = ref(null)
const secretAccessKeyRef = ref(null)

const secretKeys = new Set([
  'DATABASE_URL',
  'AMAP_KEY',
  'AMAP_JS_KEY',
  'AMAP_SECURITY_JS_CODE',
  'ACCESS_KEY_ID',
  'SECRET_ACCESS_KEY'
])

const secretMask = '••••••••••••••••'
const settingsFlags = reactive({})
const secretDisplay = reactive({
  DATABASE_URL: '',
  AMAP_KEY: '',
  AMAP_JS_KEY: '',
  AMAP_SECURITY_JS_CODE: '',
  ACCESS_KEY_ID: '',
  SECRET_ACCESS_KEY: ''
})
const secretRefs = {
  DATABASE_URL: databaseUrlRef,
  AMAP_KEY: amapKeyRef,
  AMAP_JS_KEY: amapJsKeyRef,
  AMAP_SECURITY_JS_CODE: amapSecurityRef,
  ACCESS_KEY_ID: accessKeyRef,
  SECRET_ACCESS_KEY: secretAccessKeyRef
}

const form = reactive({
  DATABASE_URL: '',
  AMAP_KEY: '',
  AMAP_JS_KEY: '',
  AMAP_SECURITY_JS_CODE: '',
  ACCESS_KEY_ID: '',
  SECRET_ACCESS_KEY: '',
  BUCKET_NAME: '',
  UPLOAD_PATH: '',
  REGION: '',
  ENDPOINT: '',
  ACL: '',
  OUTPUT_URL_PATTERN: '',
  API_BASE_URL: '',
  FRONTEND_ORIGINS: ''
})

function applySettings(payload) {
  if (!payload) return
  const flags = payload.flags || {}
  Object.keys(form).forEach((key) => {
    if (secretKeys.has(key)) {
      form[key] = ''
      secretDisplay[key] = flags[`${key}_set`] ? secretMask : ''
      return
    }
    if (key in payload) {
      form[key] = payload[key] || ''
    }
  })
  Object.keys(settingsFlags).forEach((key) => delete settingsFlags[key])
  Object.entries(flags).forEach(([key, value]) => {
    settingsFlags[key] = Boolean(value)
  })
}

function onSecretFocus(key, event) {
  if (secretDisplay[key] === secretMask && !form[key]) {
    event.target.select()
  }
}

function onSecretInput(key, event) {
  const value = event.target.value
  secretDisplay[key] = value
  if (value === secretMask && settingsFlags[`${key}_set`]) {
    form[key] = ''
  } else {
    form[key] = value
  }
}

function syncSecretFromRefs() {
  Object.entries(secretRefs).forEach(([key, inputRef]) => {
    const inputEl = inputRef.value
    if (!inputEl) return
    const value = inputEl.value || ''
    if (!value) {
      secretDisplay[key] = ''
      form[key] = ''
      return
    }
    if (value === secretMask && settingsFlags[`${key}_set`]) {
      secretDisplay[key] = secretMask
      form[key] = ''
      return
    }
    secretDisplay[key] = value
    form[key] = value
  })
}

async function fetchSettings() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    const resp = await fetch('/api/settings')
    if (!resp.ok) throw new Error('读取设置失败')
    const data = await resp.json()
    applySettings(data)
  } catch (err) {
    errorMessage.value = err.message || '读取设置失败'
  } finally {
    isLoading.value = false
  }
}

async function saveSettings() {
  isSaving.value = true
  successMessage.value = ''
  errorMessage.value = ''
  testMessage.value = ''
  syncSecretFromRefs()
  try {
    const resp = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config: { ...form } })
    })
    if (!resp.ok) {
      const detail = await resp.json().catch(() => null)
      throw new Error(detail?.detail || '保存失败')
    }
    const data = await resp.json()
    applySettings(data.config)
    successMessage.value = '设置已保存'
  } catch (err) {
    errorMessage.value = err.message || '保存失败'
  } finally {
    isSaving.value = false
  }
}

async function runTest(target) {
  testMessage.value = ''
  errorMessage.value = ''
  syncSecretFromRefs()
  try {
    const resp = await fetch('/api/settings/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target, config: { ...form } })
    })
    if (!resp.ok) {
      const detail = await resp.json().catch(() => null)
      throw new Error(detail?.detail || '测试失败')
    }
    const payload = await resp.json().catch(() => ({}))
    if (payload?.message) {
      testMessage.value = payload.message
    } else if (target === 'postgres') {
      testMessage.value = '数据库连接正常'
    } else if (target === 'image') {
      testMessage.value = '图床配置正常'
    } else {
      testMessage.value = 'S3 连接正常'
    }
  } catch (err) {
    errorMessage.value = err.message || '测试失败'
  }
}

onMounted(fetchSettings)
</script>

<template>
  <div class="settings-page">
    <header class="house-header">
      <div>
        <h1>系统设置</h1>
        <p>配置地图、数据库和对象存储等服务。</p>
      </div>
      <RouterLink class="ghost-link" to="/">返回导航</RouterLink>
    </header>
    <div class="settings-body">
      <div v-if="isLoading" class="settings-loading">正在读取设置...</div>
      <div v-else>
        <div v-if="successMessage" class="settings-success">{{ successMessage }}</div>
        <div v-if="testMessage" class="settings-success">{{ testMessage }}</div>
        <div v-if="errorMessage" class="house-error">{{ errorMessage }}</div>
        <form class="settings-form" @submit.prevent="saveSettings">
          <section class="settings-section">
            <div class="settings-section-header">
              <div>
                <h2>基础配置</h2>
                <p>影响前端与后端通讯的配置。</p>
              </div>
            </div>
            <div class="settings-grid">
              <label class="settings-field">
                API_BASE_URL
                <input v-model="form.API_BASE_URL" type="text" placeholder="http://localhost:8000" />
              </label>
              <label class="settings-field">
                FRONTEND_ORIGINS
                <input v-model="form.FRONTEND_ORIGINS" type="text" placeholder="http://localhost:5173" />
              </label>
            </div>
          </section>

          <section class="settings-section">
            <div class="settings-section-header">
              <div>
                <h2>地图服务</h2>
                <p>用于地图加载与坐标查询。</p>
              </div>
            </div>
            <div class="settings-grid">
              <label class="settings-field">
                AMAP_KEY
                <input
                  :value="secretDisplay.AMAP_KEY"
                  type="password"
                  ref="amapKeyRef"
                  @focus="onSecretFocus('AMAP_KEY', $event)"
                  @input="onSecretInput('AMAP_KEY', $event)"
                />
              </label>
              <label class="settings-field">
                AMAP_JS_KEY
                <input
                  :value="secretDisplay.AMAP_JS_KEY"
                  type="password"
                  ref="amapJsKeyRef"
                  @focus="onSecretFocus('AMAP_JS_KEY', $event)"
                  @input="onSecretInput('AMAP_JS_KEY', $event)"
                />
              </label>
              <label class="settings-field">
                AMAP_SECURITY_JS_CODE
                <input
                  :value="secretDisplay.AMAP_SECURITY_JS_CODE"
                  type="password"
                  ref="amapSecurityRef"
                  @focus="onSecretFocus('AMAP_SECURITY_JS_CODE', $event)"
                  @input="onSecretInput('AMAP_SECURITY_JS_CODE', $event)"
                />
              </label>
            </div>
          </section>

          <section class="settings-section">
            <div class="settings-section-header">
              <div>
                <h2>数据库</h2>
                <p>用于房屋管理等功能的持久化。</p>
              </div>
            </div>
            <div class="settings-grid">
              <label class="settings-field">
                DATABASE_URL
                <input
                  :value="secretDisplay.DATABASE_URL"
                  type="password"
                  ref="databaseUrlRef"
                  @focus="onSecretFocus('DATABASE_URL', $event)"
                  @input="onSecretInput('DATABASE_URL', $event)"
                />
              </label>
            </div>
          </section>

          <section class="settings-section">
            <div class="settings-section-header">
              <div>
                <h2>对象存储</h2>
                <p>用于上传房源图片与资料。</p>
              </div>
            </div>
            <div class="settings-grid">
              <label class="settings-field">
                ACCESS_KEY_ID
                <input
                  :value="secretDisplay.ACCESS_KEY_ID"
                  type="password"
                  ref="accessKeyRef"
                  @focus="onSecretFocus('ACCESS_KEY_ID', $event)"
                  @input="onSecretInput('ACCESS_KEY_ID', $event)"
                />
              </label>
              <label class="settings-field">
                SECRET_ACCESS_KEY
                <input
                  :value="secretDisplay.SECRET_ACCESS_KEY"
                  type="password"
                  ref="secretAccessKeyRef"
                  @focus="onSecretFocus('SECRET_ACCESS_KEY', $event)"
                  @input="onSecretInput('SECRET_ACCESS_KEY', $event)"
                />
              </label>
              <label class="settings-field">
                BUCKET_NAME
                <input v-model="form.BUCKET_NAME" type="text" placeholder="myimage" />
              </label>
              <label class="settings-field">
                UPLOAD_PATH
                <input v-model="form.UPLOAD_PATH" type="text" placeholder="house-images" />
              </label>
              <label class="settings-field">
                REGION
                <input v-model="form.REGION" type="text" placeholder="auto" />
              </label>
              <label class="settings-field">
                ENDPOINT
                <input
                  v-model="form.ENDPOINT"
                  type="text"
                  placeholder="https://<account_id>.r2.cloudflarestorage.com"
                />
              </label>
              <label class="settings-field">
                ACL
                <input v-model="form.ACL" type="text" placeholder="default" />
              </label>
              <label class="settings-field">
                OUTPUT_URL_PATTERN
                <input
                  v-model="form.OUTPUT_URL_PATTERN"
                  type="text"
                  placeholder="https://cdn.example.com/{key}"
                />
              </label>
            </div>
          </section>

          <div class="settings-actions">
            <button type="button" @click="runTest('postgres')" :disabled="isSaving">
              测试数据库连接
            </button>
            <button type="button" @click="runTest('image')" :disabled="isSaving">
              测试图床配置
            </button>
            <button type="submit" :disabled="isSaving">
              {{ isSaving ? '保存中...' : '保存设置' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>
