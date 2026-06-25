<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/api/request'

// 药师处方双盲审核 + 审方历史 + 病历详情（PRD §3.4）
const tab = ref('pending')
const list = ref([])
const loading = ref(false)
const drawer = ref(false)
const current = ref({})

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
      id: rx.id, order: rx.order_id, patient: rx.patient_name, doctor: rx.doctor_name, dept: rx.dept,
      diagnosis: rx.diagnosis, chief: rx.chief, present: rx.present_illness, advice: rx.advice,
      items: rx.items || [], status: rx.audit_status, reason: rx.reject_reason, time: rx.created_at,
      drugs: (rx.items || []).map((it) => `${it.name} x${it.qty}`).join('；')
    }))
  } finally {
    loading.value = false
  }
}
onMounted(load)
function switchTab(k) { tab.value = k; load() }
function detail(row) { current.value = row; drawer.value = true }

// 通过 → 触发 CA 加签生效（AUDITING -> PRESCRIBED）
async function approve(row) {
  await request.post(`/prescriptions/${row.id}/approve`)
  ElMessage.success(`处方 ${row.id} 审核通过，已触发 CA 数字签名`)
  drawer.value = false
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
    drawer.value = false
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
      <el-table-column prop="id" label="处方号" width="90" />
      <el-table-column prop="order" label="订单号" width="90" />
      <el-table-column prop="patient" label="患者" width="80" />
      <el-table-column prop="doctor" label="开方医生" width="100" />
      <el-table-column prop="diagnosis" label="临床诊断" width="150" />
      <el-table-column prop="drugs" label="药品明细" min-width="160" show-overflow-tooltip />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="(STATUS[row.status] || {}).type">{{ (STATUS[row.status] || {}).t || row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="time" label="提交时间" width="140" />
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="detail(row)">病历详情</el-button>
          <template v-if="row.status === 'pending'">
            <el-button size="small" type="success" @click="approve(row)">通过</el-button>
            <el-button size="small" type="danger" @click="reject(row)">驳回</el-button>
          </template>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <!-- 病历 / 处方详情 -->
  <el-drawer v-model="drawer" :title="`处方 #${current.id} · 病历详情`" size="520px">
    <el-descriptions :column="2" border>
      <el-descriptions-item label="患者">{{ current.patient }}</el-descriptions-item>
      <el-descriptions-item label="开方医生">{{ current.doctor }}<span v-if="current.dept" class="muted"> / {{ current.dept }}</span></el-descriptions-item>
      <el-descriptions-item label="订单号">{{ current.order }}</el-descriptions-item>
      <el-descriptions-item label="提交时间">{{ current.time }}</el-descriptions-item>
      <el-descriptions-item label="状态" :span="2">
        <el-tag :type="(STATUS[current.status] || {}).type">{{ (STATUS[current.status] || {}).t || current.status }}</el-tag>
        <span v-if="current.reason" class="reason">驳回原因：{{ current.reason }}</span>
      </el-descriptions-item>
    </el-descriptions>

    <el-descriptions title="电子病历" :column="1" border class="mt">
      <el-descriptions-item label="主诉">{{ current.chief || '—' }}</el-descriptions-item>
      <el-descriptions-item label="现病史">{{ current.present || '—' }}</el-descriptions-item>
      <el-descriptions-item label="临床诊断">{{ current.diagnosis || '—' }}</el-descriptions-item>
      <el-descriptions-item label="医嘱">{{ current.advice || '—' }}</el-descriptions-item>
    </el-descriptions>

    <div class="sec-title">处方药品</div>
    <el-table :data="current.items" size="small" border>
      <el-table-column prop="name" label="药品" />
      <el-table-column prop="spec" label="规格" width="110" />
      <el-table-column prop="qty" label="数量" width="60" />
      <el-table-column prop="usage" label="用法用量" min-width="120" />
    </el-table>

    <div v-if="current.status === 'pending'" class="drawer-foot">
      <el-button type="success" @click="approve(current)">通过并 CA 加签</el-button>
      <el-button type="danger" @click="reject(current)">驳回</el-button>
    </div>
  </el-drawer>
</template>

<style scoped>
.hd { display: flex; align-items: center; justify-content: space-between; }
.reason { color: #fa5151; font-size: 13px; margin-left: 10px; }
.muted { color: var(--el-text-color-secondary); }
.mt { margin-top: 18px; }
.sec-title { font-weight: 600; margin: 18px 0 10px; }
.drawer-foot { margin-top: 22px; display: flex; gap: 12px; }
</style>
