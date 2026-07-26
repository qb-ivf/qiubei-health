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
const isAdmin = localStorage.getItem('role') === 'admin'

const TABS = [
  { k: 'pending', t: '待审核' },
  { k: 'approved', t: '已通过' },
  { k: 'rejected', t: '已驳回' },
  { k: 'manual_review', t: 'CA待确认' },
  { k: 'all', t: '全部' }
]
const STATUS = {
  pending: { t: '待审核', type: 'info' },
  approved: { t: '已通过', type: 'success' },
  rejected: { t: '已驳回', type: 'danger' },
  not_required: { t: '仅病历', type: 'warning' }
}
const CA_STATUS = {
  manual_review: { t: '结果待人工确认', type: 'danger' },
  failed: { t: '签署失败，可重试', type: 'warning' },
  verified: { t: '三方验签通过', type: 'success' }
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
      caStatus: rx.ca_sign_status, recordOnly: !!rx.record_only,
      drugs: (rx.items || []).map((it) => `${it.name} x${it.qty}`).join('；')
    }))
  } finally {
    loading.value = false
  }
}
onMounted(load)
function switchTab(k) { tab.value = k; load() }
function detail(row) { current.value = row; drawer.value = true }

// 通过审方（AUDITING -> PRESCRIBED）。CA 双录与 PDF 文档签署是两个独立步骤。
async function approve(row) {
  if (row.caStatus === 'manual_review') {
    ElMessage.error('放心签结果待人工确认，当前禁止重复签署')
    return
  }
  await request.post(`/prescriptions/${row.id}/approve`)
  ElMessage.success(`处方 ${row.id} 审核通过`)
  drawer.value = false
  load()
}

// 驳回 → 必填驳回原因（AUDITING -> REJECTED）
function reject(row) {
  if (row.caStatus === 'manual_review') {
    ElMessage.error('放心签结果待人工确认，当前禁止驳回')
    return
  }
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

function resolveCa(row) {
  ElMessageBox.prompt(
    '必须先向放心签确认本次未生成签署结果。请填写工单号或脱敏后的确认说明；不得填写身份证、密钥或 token。',
    '解除 CA 签署锁定',
    {
      confirmButtonText: '已确认未签署并解锁',
      cancelButtonText: '取消',
      inputPlaceholder: '例如：工单 FXQ-123 已确认未生成合同',
      inputValidator: (v) => {
        const note = (v || '').trim()
        return note.length >= 5 && note.length <= 240 ? true : '确认说明应为 5–240 个字符'
      }
    }
  ).then(async ({ value }) => {
    await request.post(`/admin/prescriptions/${row.id}/ca-manual-review`, {
      confirmed_not_signed: true,
      note: value.trim()
    })
    ElMessage.success(`诊疗文档 ${row.id} 已解除 CA 签署锁定`)
    drawer.value = false
    load()
  }).catch(() => {})
}
</script>

<template>
  <el-card>
    <template #header>
      <div class="hd">
        <span>处方审核与 CA 异常（双盲分发，含审核历史）</span>
        <el-radio-group :model-value="tab" @change="switchTab">
          <el-radio-button v-for="t in TABS" :key="t.k" :value="t.k">{{ t.t }}</el-radio-button>
        </el-radio-group>
      </div>
    </template>
    <el-table :data="list" v-loading="loading">
      <el-table-column prop="id" label="文档号" width="90" />
      <el-table-column prop="order" label="订单号" width="90" />
      <el-table-column prop="patient" label="患者" width="80" />
      <el-table-column prop="doctor" label="接诊医生" width="100" />
      <el-table-column prop="diagnosis" label="临床诊断" width="150" />
      <el-table-column prop="drugs" label="药品明细" min-width="160" show-overflow-tooltip />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="(STATUS[row.status] || {}).type">{{ (STATUS[row.status] || {}).t || row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="CA 签署" width="145">
        <template #default="{ row }">
          <el-tag v-if="row.caStatus" :type="(CA_STATUS[row.caStatus] || {}).type || 'info'">
            {{ (CA_STATUS[row.caStatus] || {}).t || row.caStatus }}
          </el-tag>
          <span v-else class="muted">未发起</span>
        </template>
      </el-table-column>
      <el-table-column prop="time" label="提交时间" width="140" />
      <el-table-column label="操作" width="300" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="detail(row)">病历详情</el-button>
          <template v-if="row.status === 'pending'">
            <el-button size="small" type="success" :disabled="row.caStatus === 'manual_review'" @click="approve(row)">通过</el-button>
            <el-button size="small" type="danger" :disabled="row.caStatus === 'manual_review'" @click="reject(row)">驳回</el-button>
          </template>
          <el-button
            v-if="isAdmin && row.caStatus === 'manual_review'"
            size="small"
            type="warning"
            @click="resolveCa(row)"
          >人工确认</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <!-- 病历 / 处方详情 -->
  <el-drawer v-model="drawer" :title="`${current.recordOnly ? '电子病历' : '处方'} #${current.id} · 详情`" size="520px">
    <el-descriptions :column="2" border>
      <el-descriptions-item label="患者">{{ current.patient }}</el-descriptions-item>
      <el-descriptions-item label="接诊医生">{{ current.doctor }}<span v-if="current.dept" class="muted"> / {{ current.dept }}</span></el-descriptions-item>
      <el-descriptions-item label="订单号">{{ current.order }}</el-descriptions-item>
      <el-descriptions-item label="提交时间">{{ current.time }}</el-descriptions-item>
      <el-descriptions-item label="状态" :span="2">
        <el-tag :type="(STATUS[current.status] || {}).type">{{ (STATUS[current.status] || {}).t || current.status }}</el-tag>
        <span v-if="current.reason" class="reason">驳回原因：{{ current.reason }}</span>
      </el-descriptions-item>
      <el-descriptions-item label="CA 签署" :span="2">
        <el-tag v-if="current.caStatus" :type="(CA_STATUS[current.caStatus] || {}).type || 'info'">
          {{ (CA_STATUS[current.caStatus] || {}).t || current.caStatus }}
        </el-tag>
        <span v-else>未发起</span>
      </el-descriptions-item>
    </el-descriptions>

    <el-alert
      v-if="current.caStatus === 'manual_review'"
      type="error"
      :closable="false"
      show-icon
      class="mt"
      title="供应商返回结果不确定，已禁止重复签署。"
      description="请由管理员联系放心签确认本次未生成签署结果，记录工单说明后再解除锁定。"
    />

    <el-descriptions title="电子病历" :column="1" border class="mt">
      <el-descriptions-item label="主诉">{{ current.chief || '—' }}</el-descriptions-item>
      <el-descriptions-item label="现病史">{{ current.present || '—' }}</el-descriptions-item>
      <el-descriptions-item label="临床诊断">{{ current.diagnosis || '—' }}</el-descriptions-item>
      <el-descriptions-item label="医嘱">{{ current.advice || '—' }}</el-descriptions-item>
    </el-descriptions>

    <div v-if="!current.recordOnly" class="sec-title">处方药品</div>
    <el-table v-if="!current.recordOnly" :data="current.items" size="small" border>
      <el-table-column prop="name" label="药品" />
      <el-table-column prop="spec" label="规格" width="110" />
      <el-table-column prop="qty" label="数量" width="60" />
      <el-table-column prop="usage" label="用法用量" min-width="120" />
    </el-table>

    <div v-if="current.status === 'pending'" class="drawer-foot">
      <el-button type="success" :disabled="current.caStatus === 'manual_review'" @click="approve(current)">通过审方</el-button>
      <el-button type="danger" :disabled="current.caStatus === 'manual_review'" @click="reject(current)">驳回</el-button>
    </div>
    <div v-if="isAdmin && current.caStatus === 'manual_review'" class="drawer-foot">
      <el-button type="warning" @click="resolveCa(current)">人工确认并解锁</el-button>
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
