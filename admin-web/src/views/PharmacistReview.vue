<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/api/request'

// 药师处方双盲审核 + 审方历史（PRD §3.4）
const tab = ref('pending')
const list = ref([])
const loading = ref(false)

const TABS = [
  { k: 'pending', t: '待审核' },
  { k: 'approved', t: '已通过' },
  { k: 'rejected', t: '已驳回' },
  { k: 'all', t: '全部' }
]
const STATUS = {
  pending: { t: '待审核', type: 'info' },
  approved: { t: '已通过', type: 'success' },
  rejected: { t: '已驳回', type: 'danger' }
}

async function load() {
  loading.value = true
  try {
    const q = tab.value === 'all' ? '' : `?status=${tab.value}`
    const data = await request.get(`/admin/prescriptions${q}`)
    list.value = (data || []).map((rx) => ({
      id: rx.id, order: rx.order_id, patient: rx.patient_name, doctor: rx.doctor_name,
      diagnosis: rx.diagnosis, status: rx.audit_status, reason: rx.reject_reason, time: rx.created_at,
      drugs: (rx.items || []).map((it) => `${it.name} x${it.qty}`).join('；')
    }))
  } finally {
    loading.value = false
  }
}
onMounted(load)
function switchTab(k) { tab.value = k; load() }

// 通过 → 触发 CA 加签生效（AUDITING -> PRESCRIBED）
async function approve(row) {
  await request.post(`/prescriptions/${row.id}/approve`)
  ElMessage.success(`处方 ${row.id} 审核通过，已触发 CA 数字签名`)
  load()
}

// 驳回 → 必填驳回原因（AUDITING -> REJECTED）
function reject(row) {
  ElMessageBox.prompt('请填写驳回原因（如：抗生素用量超标、诊断与用药不符）', '驳回处方', {
    confirmButtonText: '确认驳回', cancelButtonText: '取消',
    inputValidator: (v) => (v && v.trim() ? true : '驳回原因不能为空')
  }).then(async ({ value }) => {
    await request.post(`/prescriptions/${row.id}/reject`, { reason: value })
    ElMessage.warning(`处方 ${row.id} 已驳回：${value}`)
    load()
  }).catch(() => {})
}
</script>

<template>
  <el-card>
    <template #header>
      <div class="hd">
        <span>处方审核队列（双盲分发，含审核历史）</span>
        <el-radio-group :model-value="tab" @change="switchTab">
          <el-radio-button v-for="t in TABS" :key="t.k" :value="t.k">{{ t.t }}</el-radio-button>
        </el-radio-group>
      </div>
    </template>
    <el-table :data="list" v-loading="loading">
      <el-table-column prop="id" label="处方号" width="100" />
      <el-table-column prop="order" label="订单号" width="100" />
      <el-table-column prop="patient" label="患者" width="90" />
      <el-table-column prop="doctor" label="开方医生" width="100" />
      <el-table-column prop="diagnosis" label="临床诊断" width="160" />
      <el-table-column prop="drugs" label="药品明细" min-width="180" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="(STATUS[row.status] || {}).type">{{ (STATUS[row.status] || {}).t || row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="time" label="提交时间" width="140" />
      <el-table-column label="操作 / 备注" width="200">
        <template #default="{ row }">
          <template v-if="row.status === 'pending'">
            <el-button size="small" type="success" @click="approve(row)">通过</el-button>
            <el-button size="small" type="danger" @click="reject(row)">驳回</el-button>
          </template>
          <span v-else-if="row.status === 'rejected'" class="reason">驳回原因：{{ row.reason || '—' }}</span>
          <span v-else class="muted">已通过 · CA 已加签</span>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<style scoped>
.hd { display: flex; align-items: center; justify-content: space-between; }
.reason { color: #fa5151; font-size: 13px; }
.muted { color: #909399; font-size: 13px; }
</style>
