<script setup>
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

// 药师处方双盲审核（PRD §3.4）
const list = ref([
  { id: 'RX20260621A', patient: '王*明', doctor: '张建设', diagnosis: '急性上呼吸道感染',
    drugs: '阿莫西林胶囊 x1；布洛芬缓释胶囊 x1' },
  { id: 'RX20260621B', patient: '李*', doctor: '王美丽', diagnosis: '急性支气管炎',
    drugs: '头孢克肟 x1' }
])

// 通过 → 触发 CA 加签生效（AUDITING -> PRESCRIBED）
function approve(row) {
  ElMessage.success(`处方 ${row.id} 审核通过，已触发 CA 数字签名`)
  list.value = list.value.filter((r) => r.id !== row.id)
}

// 驳回 → 必填驳回原因（AUDITING -> REJECTED），微信模板消息通知医生
function reject(row) {
  ElMessageBox.prompt('请填写驳回原因（如：抗生素用量超标、诊断与用药不符）', '驳回处方', {
    confirmButtonText: '确认驳回', cancelButtonText: '取消',
    inputValidator: (v) => (v && v.trim() ? true : '驳回原因不能为空')
  }).then(({ value }) => {
    ElMessage.warning(`处方 ${row.id} 已驳回：${value}`)
    list.value = list.value.filter((r) => r.id !== row.id)
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
