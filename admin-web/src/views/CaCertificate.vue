<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/api/request'

const config = ref({ enabled: false, required: false, ready: false, errors: [] })
const enrollment = ref(null)
const loading = ref(false)
const polling = ref(false)
let timer = null

const STATUS = {
  pending: { text: '等待完成智能双录', type: 'warning' },
  succeeded: { text: 'CA协议及智能双录已完成', type: 'success' },
  failed: { text: '本次核验未通过', type: 'danger' },
  expired: { text: '核验链接已过期', type: 'info' }
}
const state = computed(() => STATUS[enrollment.value?.status] || { text: '尚未发起', type: 'info' })

async function load() {
  loading.value = true
  try {
    config.value = await request.get('/ca/config')
    try { enrollment.value = await request.get('/ca/enrollments/latest') } catch (_) { enrollment.value = null }
  } finally {
    loading.value = false
  }
}

async function start() {
  if (!config.value.ready) {
    ElMessage.error((config.value.errors || []).join('；') || '放心签尚未配置')
    return
  }
  const popup = window.open('about:blank', 'fxq-ca')
  loading.value = true
  try {
    const result = await request.post('/ca/enrollments')
    enrollment.value = result
    if (result.agreement_url) {
      if (popup) popup.location.replace(result.agreement_url)
      else ElMessage.warning('浏览器已拦截弹窗，请允许本站打开新窗口后重试')
    } else {
      if (popup) popup.close()
      ElMessage.success('当前账号已经完成核验')
    }
  } catch (err) {
    if (popup) popup.close()
  } finally {
    loading.value = false
  }
}

async function refresh(attempt = 0) {
  if (!enrollment.value?.order_no || enrollment.value.status !== 'pending' || polling.value) return
  polling.value = true
  try {
    enrollment.value = await request.post(`/ca/enrollments/${enrollment.value.order_no}/refresh`)
    if (enrollment.value.status === 'succeeded') ElMessage.success('CA 智能双录核验成功')
    else if (enrollment.value.status === 'pending' && attempt < 2) {
      timer = window.setTimeout(() => refresh(attempt + 1), 10000)
    }
  } finally {
    polling.value = false
  }
}

function onFocus() {
  if (enrollment.value?.status === 'pending') refresh()
}

onMounted(() => {
  load()
  window.addEventListener('focus', onFocus)
})
onBeforeUnmount(() => {
  window.removeEventListener('focus', onFocus)
  if (timer) window.clearTimeout(timer)
})
</script>

<template>
  <el-card v-loading="loading">
    <template #header>
      <div class="header">
        <span>个人 CA 数字证书</span>
        <el-tag :type="state.type">{{ state.text }}</el-tag>
      </div>
    </template>

    <el-alert
      v-if="!config.ready"
      type="warning"
      :closable="false"
      title="放心签接口尚未就绪"
      :description="(config.errors || []).join('；') || '请联系管理员配置接口'"
      show-icon
    />

    <el-result
      :icon="enrollment?.status === 'succeeded' ? 'success' : 'info'"
      :title="state.text"
      sub-title="请由药师本人阅读 CA 协议，并完成人脸活体检测和意愿回答"
    >
      <template #extra>
        <el-button
          v-if="!enrollment || ['failed', 'expired'].includes(enrollment.status)"
          type="primary"
          :loading="loading"
          @click="start"
        >{{ enrollment ? '重新发起核验' : '开始 CA 核验' }}</el-button>
        <el-button
          v-else-if="enrollment.status === 'pending'"
          type="primary"
          :loading="polling"
          @click="refresh(0)"
        >查询核验结果</el-button>
      </template>
    </el-result>

    <el-descriptions v-if="enrollment" :column="2" border>
      <el-descriptions-item label="业务流水">{{ enrollment.order_no }}</el-descriptions-item>
      <el-descriptions-item label="平台核验ID">{{ enrollment.verify_id || '—' }}</el-descriptions-item>
      <el-descriptions-item label="活体得分">{{ enrollment.live_rate || '—' }}</el-descriptions-item>
      <el-descriptions-item label="人脸相似度">{{ enrollment.similarity || '—' }}</el-descriptions-item>
      <el-descriptions-item label="平台结果" :span="2">{{ enrollment.provider_msg || '—' }}</el-descriptions-item>
    </el-descriptions>

    <el-alert
      class="privacy"
      type="info"
      :closable="false"
      title="隐私保护"
      description="身份证信息只由后端解密后提交给放心签；本页面不接收身份证号，系统也不会拉取或保存刷脸照片和视频。"
      show-icon
    />
  </el-card>
</template>

<style scoped>
.header { display: flex; align-items: center; justify-content: space-between; }
.privacy { margin-top: 20px; }
</style>
