<script setup>
import { onMounted, reactive, ref } from 'vue'

const config = reactive({})
const secretDisplay = reactive({})
const loading = ref(true)
const saving = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const testing = reactive({ postgres: false, s3: false })

const secretMask = '●●●●●●●●●●●●●●●●●●'
const secretKeys = new Set([
  'DATABASE_URL',
  'AWS_ACCESS_KEY_ID',
  'AWS_SECRET_ACCESS_KEY',
  'AMAP_KEY',
  'AMAP_JS_KEY',
  'AMAP_SECURITY_JS_CODE'
])

const sections = [
  {
    title: 'PostgreSQL',
    target: 'postgres',
    description: '用于房屋管理与历史数据存储',
    fields: [
      { key: 'DATABASE_URL', label: 'DATABASE_URL', secret: true }
    ]
  },
  {
    title: 'Amazon S3',
    target: 's3',
    description: '图片上传存储',
    fields: [
      { key: 'AWS_ACCESS_KEY_ID', label: 'AWS_ACCESS_KEY_ID', secret: true },
      { key: 'AWS_SECRET_ACCESS_KEY', label: 'AWS_SECRET_ACCESS_KEY', secret: true },
      { key: 'AWS_REGION', label: 'AWS_REGION' },
      { key: 'AWS_DEFAULT_REGION', label: 'AWS_DEFAULT_REGION' },
      { key: 'S3_BUCKET', label: 'S3_BUCKET' },
      { key: 'S3_PUBLIC_BASE_URL', label: 'S3_PUBLIC_BASE_URL' }
    ]
  },
  {
    title: '地图与前端',
    description: '高德地图与前端配置',
    fields: [
      { key: 'AMAP_KEY', label: 'AMAP_KEY', secret: true },
      { key: 'AMAP_JS_KEY', label: 'AMAP_JS_KEY', secret: true },
      { key: 'AMAP_SECURITY_JS_CODE', label: 'AMAP_SECURITY_JS_CODE', secret: true },
      { key: 'API_BASE_URL', label: 'API_BASE_URL' },
      { key: 'FRONTEND_ORIGINS', label: 'FRONTEND_ORIGINS' }
    ]
  }
]

async function loadSettings() {
  errorMessage.value = ''
  successMessage.value = ''
  loading.value = true
  try {
    const resp = await fetch('/api/settings')
    if (!resp.ok) throw new Error('读取配置失败')
    const payload = await resp.json()
    Object.assign(config, payload)
    Object.keys(config).forEach((key) => {
      if (secretKeys.has(key)) {
        config[key] = ''
      }
    })
    secretKeys.forEach((key) => {
      if (config.flags?.[`${key}_set`]) {
        secretDisplay[key] = secretMask
      } else {
        secretDisplay[key] = ''
      }
    })
  } catch (err) {
    errorMessage.value = err.message || '读取配置失败'
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  errorMessage.value = ''
  successMessage.value = ''
  saving.value = true
  try {
    const payload = { config: { ...config } }
    secretKeys.forEach((key) => {
      if (!config[key]) {
        delete payload.config[key]
      }
    })
    const resp = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    if (!resp.ok) {
      const payload = await resp.json().catch(() => ({}))
      throw new Error(payload?.detail || '保存失败')
    }
    successMessage.value = '保存成功，正在重载...'
    setTimeout(() => {
      window.location.reload()
    }, 600)
  } catch (err) {
    errorMessage.value = err.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function testConfig(target) {
  errorMessage.value = ''
  successMessage.value = ''
  testing[target] = true
  try {
    const resp = await fetch('/api/settings/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target, config })
    })
    if (!resp.ok) {
      const payload = await resp.json().catch(() => ({}))
      throw new Error(payload?.detail || '测试失败')
    }
    successMessage.value = `测试通过: ${target}`
  } catch (err) {
    errorMessage.value = err.message || '测试失败'
  } finally {
    testing[target] = false
  }
}

function handleSecretKeydown(key, event) {
  if (secretDisplay[key] !== secretMask) return
  if (event.key === 'Tab' || event.key === 'Shift') return
  secretDisplay[key] = ''
  config[key] = ''
}

function handleSecretInput(key, event) {
  secretDisplay[key] = event.target.value
  config[key] = event.target.value
}

onMounted(loadSettings)
</script>

<template>
  <div class="settings-page">
    <header class="house-header">
      <div>
        <h1>设置</h1>
        <p>读取并修改 .env 配置，保存后自动重载。</p>
      </div>
      <RouterLink class="ghost-link" to="/">返回导航</RouterLink>
    </header>

    <section class="settings-body">
      <div v-if="loading" class="settings-loading">配置读取中...</div>
      <div v-if="errorMessage" class="house-error">{{ errorMessage }}</div>
      <div v-if="successMessage" class="settings-success">{{ successMessage }}</div>

      <form v-if="!loading" class="settings-form" @submit.prevent="saveSettings">
        <div v-for="section in sections" :key="section.title" class="settings-section">
          <header class="settings-section-header">
            <div>
              <h2>{{ section.title }}</h2>
              <p>{{ section.description }}</p>
            </div>
            <button
              v-if="section.target"
              type="button"
              class="ghost-link"
              :disabled="testing[section.target]"
              @click="testConfig(section.target)"
            >
              {{ testing[section.target] ? '测试中...' : '测试连接' }}
            </button>
          </header>
          <div class="settings-grid">
            <label v-for="field in section.fields" :key="field.key" class="settings-field">
              <span>{{ field.label }}</span>
              <input
                v-if="field.secret"
                :type="'password'"
                :value="secretDisplay[field.key]"
                @keydown="(event) => handleSecretKeydown(field.key, event)"
                @input="(event) => handleSecretInput(field.key, event)"
              />
              <input
                v-else
                v-model="config[field.key]"
                type="text"
              />
            </label>
          </div>
        </div>
        <div class="settings-actions">
          <button type="submit" :disabled="saving">
            {{ saving ? '保存中...' : '保存并重载' }}
          </button>
        </div>
      </form>
    </section>
  </div>
</template>
