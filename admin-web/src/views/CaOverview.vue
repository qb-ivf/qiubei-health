<script setup>
import { computed, onMounted, ref } from 'vue'
import request from '@/api/request'

const loading = ref(false)
const data = ref({
  doctors: { total: 0, record_ready: 0, succeeded: 0, pending: 0, failed: 0, expired: 0, not_started: 0 },
  pharmacists: { total: 0, record_ready: 0, succeeded: 0, pending: 0, failed: 0, expired: 0, not_started: 0 },
  subjects: [],
  effective_expires_on: null,
  expiry_warning: null,
  expiry_expired: false,
  generated_at: null
})

const notReady = computed(() =>
  data.value.subjects.filter((item) => !item.record_ready).length
)
const notSucceeded = computed(() =>
  data.value.subjects.filter((item) => item.ca_status !== 'succeeded').length
)

const STATUS = {
  not_started: { text: '尚未发起', type: 'info' },
  pending: { text: '等待本人完成', type: 'warning' },
  succeeded: { text: '双录成功', type: 'success' },
  failed: { text: '核验失败', type: 'danger' },
  expired: { text: '链接过期', type: 'info' }
}

const ACCOUNT = {
  approved: '资质已通过',
  pending: '资质待审核',
  rejected: '资质未通过',
  active: '账号启用',
  disabled: '账号停用'
}

function statusOf(value) {
  return STATUS[value] || { text: value || '未知', type: 'info' }
}

function formatTime(value) {
  if (!value) return '—'
  return String(value).replace('T', ' ').replace('Z', '').slice(0, 19)
}

async function load() {
  loading.value = true
  try {
    data.value = await request.get('/ca/admin/overview')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="ca-overview">
    <div class="page-head">
      <div>
        <h2>CA 人员进度</h2>
        <p>只读汇总医师、药师的实名备案与本人双录状态，不显示身份证、核验 ID 或生物识别材料。</p>
      </div>
      <el-button type="primary" @click="load">刷新状态</el-button>
    </div>

    <el-alert
      v-if="data.expiry_warning"
      :type="data.expiry_expired ? 'error' : 'warning'"
      :title="data.expiry_expired ? 'CA 服务已到期' : 'CA 服务即将到期'"
      :description="data.expiry_warning"
      :closable="false"
      show-icon
      class="alert"
    />

    <el-alert
      type="info"
      title="管理员只能核对进度，不能代替医师或药师完成协议阅读、人脸活体和签署意愿确认。"
      :closable="false"
      show-icon
      class="alert"
    />

    <div class="metrics">
      <el-card shadow="never">
        <span>医师双录</span>
        <strong>{{ data.doctors.succeeded }} / {{ data.doctors.total }}</strong>
        <small>资料就绪 {{ data.doctors.record_ready }} 人</small>
      </el-card>
      <el-card shadow="never">
        <span>药师双录</span>
        <strong>{{ data.pharmacists.succeeded }} / {{ data.pharmacists.total }}</strong>
        <small>资料就绪 {{ data.pharmacists.record_ready }} 人</small>
      </el-card>
      <el-card shadow="never">
        <span>资料未就绪</span>
        <strong :class="{ danger: notReady }">{{ notReady }}</strong>
        <small>需先补录姓名、身份证及账号/资质</small>
      </el-card>
      <el-card shadow="never">
        <span>双录未完成</span>
        <strong :class="{ warning: notSucceeded }">{{ notSucceeded }}</strong>
        <small>必须由本人操作</small>
      </el-card>
    </div>

    <el-card shadow="never">
      <el-table :data="data.subjects" stripe empty-text="尚未导入医师或药师人员">
        <el-table-column label="人员类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.subject_type === 'doctor' ? 'primary' : 'success'" effect="plain">
              {{ row.subject_type === 'doctor' ? '医师' : '药师' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="姓名" min-width="130" />
        <el-table-column label="账号/资质" min-width="130">
          <template #default="{ row }">{{ ACCOUNT[row.account_status] || row.account_status }}</template>
        </el-table-column>
        <el-table-column label="实名资料" width="110">
          <template #default="{ row }">
            <el-tag :type="row.record_ready ? 'success' : 'danger'" effect="plain">
              {{ row.record_ready ? '已就绪' : '待补录' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="CA 双录" width="130">
          <template #default="{ row }">
            <el-tag :type="statusOf(row.ca_status).type">
              {{ statusOf(row.ca_status).text }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="平台结果" width="100">
          <template #default="{ row }">{{ row.face_code === '0' ? '成功' : (row.face_code || '—') }}</template>
        </el-table-column>
        <el-table-column label="完成时间" min-width="170">
          <template #default="{ row }">{{ formatTime(row.completed_at) }}</template>
        </el-table-column>
      </el-table>
      <div class="footnote">
        <span>较早到期日：{{ data.effective_expires_on || '未配置' }}</span>
        <span>数据生成：{{ formatTime(data.generated_at) }}</span>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.ca-overview { display: grid; gap: 16px; }
.page-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.page-head h2 { margin: 0; color: var(--el-text-color-primary); font-size: 24px; }
.page-head p { margin: 8px 0 0; color: var(--el-text-color-secondary); }
.alert { margin: 0; }
.metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.metrics :deep(.el-card__body) { display: grid; gap: 8px; }
.metrics span { color: var(--el-text-color-secondary); font-size: 13px; }
.metrics strong { color: var(--el-text-color-primary); font-size: 28px; line-height: 1; }
.metrics small { color: var(--el-text-color-placeholder); }
.metrics .danger { color: var(--el-color-danger); }
.metrics .warning { color: var(--el-color-warning); }
.footnote { display: flex; justify-content: space-between; gap: 16px; padding-top: 14px; color: var(--el-text-color-secondary); font-size: 12px; }
@media (max-width: 1000px) {
  .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
