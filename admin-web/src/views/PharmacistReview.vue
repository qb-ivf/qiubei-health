<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/api/request'

// 药师处方双盲审核（PRD §3.4）
const list = ref([])

async function load() {
  const data = await request.get('/prescriptions/pending')
  list.value = (data || []).map((rx) => ({
    id: rx.id,
    order: rx.order_id,
    patient: rx.patient_name,
    doctor: rx.doctor_name,
    diagnosis: rx.diagnosis,
    drugs: (rx.items || []).map((it) => `${it.name} x${it.qty}`).join('；')
  }))
}
onMounted(load)

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
    <template #header>待审核处方队列（双盲分发）</template>
    <el-table :data="list">
      <el-table-column prop="id" label="处方号" width="160" />
      <el-table-column prop="patient" label="患者(脱敏)" width="110" />
      <el-table-column prop="doctor" label="开方医生" width="110" />
      <el-table-column prop="diagnosis" label="临床诊断" width="180" />
      <el-table-column prop="drugs" label="药品明细" />
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button size="small" type="success" @click="approve(row)">通过</el-button>
          <el-button size="small" type="danger" @click="reject(row)">驳回</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>
