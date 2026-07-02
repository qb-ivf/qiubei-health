<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/api/request'

// 天津监管数据上报监控面板（S4）：总量/按接口维度统计、每日签到状态、失败重报、按日补采
const stats = ref([])
const byMethod = ref([])
const failed = ref([])
const enabled = ref(false)
const signin = ref(null)
const collectDay = ref('')
const payloadDialog = ref(false)
const payloadText = ref('')

const METHOD_TEXT = {
  uploadConsultIndicators: '在线咨询', uploadReferralIndicators: '在线复诊',
  uploadElectMedicalRecord: '电子病历', uploadRecipeIndicators: '在线处方',
  uploadRecipeVerificationIndicators: '处方核销', uploadBusinessInfoAfter: '评价信息',
  pushMedicalDispute: '不良事件签到', uploadDrugCatalogue: '药品目录',
}
const TYPE_TEXT = { consult: '在线咨询', referral: '在线复诊', emr: '电子病历', recipe: '在线处方',
  verification: '处方核销', evaluation: '评价', dispute_signin: '不良事件签到', drug: '药品目录',
  consultation: '问诊记录(旧)', prescription: '开药明细(旧)' }

async function load() {
  const s = await request.get('/admin/gov-reports/stats')
  enabled.value = s.enabled
  signin.value = s.signin
  stats.value = [
    { label: '上报总数', value: s.total, color: '#0056c4' },
    { label: '上报成功', value: s.success, color: '#00b578' },
    { label: '上报失败', value: s.failed, color: '#fa5151' },
    { label: '平均延迟', value: s.avg_ms + 'ms', color: '#894d00' }
  ]
  byMethod.value = (s.by_method || []).map((m) => ({ ...m, name: METHOD_TEXT[m.method] || m.method }))
  const f = await request.get('/admin/gov-reports/failed')
  failed.value = f.map((r) => ({
    id: r.id, type: TYPE_TEXT[r.type] || r.type, method: METHOD_TEXT[r.method] || r.method || '—',
    batch: r.batch_date || '—', retries: `重试 ${r.retries} 次`,
    err: r.err || r.status, payload: r.payload
  }))
}
onMounted(load)

async function retry(row) {
  await request.post(`/admin/gov-reports/${row.id}/retry`)
  ElMessage.success(`已重新投递上报 #${row.id}`)
  load()
}

function viewPayload(row) {
  payloadText.value = JSON.stringify(row.payload, null, 2) || '（无 payload）'
  payloadDialog.value = true
}

async function collect() {
  if (!collectDay.value) { ElMessage.warning('请选择要补采的日期'); return }
  const res = await request.post('/admin/gov-reports/collect', { day: collectDay.value })
  ElMessage.success(`已补采 ${res.day}：` + Object.entries(res.counts).map(([k, v]) => `${k}=${v}`).join(' '))
  load()
}
</script>

<template>
  <el-row :gutter="16">
    <el-col :span="6" v-for="s in stats" :key="s.label">
      <el-card>
        <div class="stat__label">{{ s.label }}</div>
        <div class="stat__value" :style="{ color: s.color }">{{ s.value }}</div>
      </el-card>
    </el-col>
  </el-row>

  <el-card class="mt">
    <template #header>
      <div class="hd">
        <span>
          按接口统计
          <el-tag v-if="enabled" type="success" size="small" style="margin-left:8px">真实上报已启用</el-tag>
          <el-tag v-else type="info" size="small" style="margin-left:8px">本地模拟（TJ_REPORT_ENABLED=false）</el-tag>
          <el-tag v-if="signin" :type="signin.status === 'success' ? 'success' : 'warning'" size="small" style="margin-left:8px">
            不良事件签到 {{ signin.batch_date }}：{{ signin.status === 'success' ? '已签到' : signin.status }}
          </el-tag>
        </span>
        <span class="collect">
          <el-date-picker v-model="collectDay" type="date" value-format="YYYY-MM-DD" placeholder="选择补采日期" size="small" style="width:160px" />
          <el-button size="small" type="primary" @click="collect">按日补采</el-button>
        </span>
      </div>
    </template>
    <el-table :data="byMethod">
      <el-table-column prop="name" label="监管接口" width="140" />
      <el-table-column prop="method" label="X-Service-Method" show-overflow-tooltip />
      <el-table-column prop="total" label="总数" width="80" />
      <el-table-column prop="success" label="成功" width="80" />
      <el-table-column prop="pending" label="待发" width="80" />
      <el-table-column label="失败/死信" width="110">
        <template #default="{ row }">
          <span :style="{ color: row.failed + row.dead > 0 ? '#fa5151' : '' }">{{ row.failed + row.dead }}</span>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-card class="mt">
    <template #header>失败任务（数据错误改数后可一键重报）</template>
    <el-table :data="failed">
      <el-table-column prop="id" label="#" width="70" />
      <el-table-column prop="method" label="接口" width="110" />
      <el-table-column prop="batch" label="批次" width="110" />
      <el-table-column prop="retries" label="重试" width="100" />
      <el-table-column prop="err" label="失败原因" show-overflow-tooltip />
      <el-table-column label="操作" width="190">
        <template #default="{ row }">
          <el-button size="small" @click="viewPayload(row)">看报文</el-button>
          <el-button size="small" type="primary" @click="retry(row)">重新上报</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="payloadDialog" title="上报报文（入队时快照）" width="640px">
    <pre class="payload">{{ payloadText }}</pre>
  </el-dialog>
</template>

<style scoped>
.stat__label { color: #909399; font-size: 13px; }
.stat__value { font-size: 28px; font-weight: 700; margin-top: 8px; }
.mt { margin-top: 16px; }
.hd { display: flex; align-items: center; justify-content: space-between; }
.collect { display: flex; gap: 8px; align-items: center; }
.payload { max-height: 60vh; overflow: auto; background: var(--el-fill-color-light); padding: 12px; border-radius: 6px; font-size: 12px; }
</style>
