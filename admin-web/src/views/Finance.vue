<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/api/request'

// 财务对账、渠道分账与提现审批（PRD §4.3）
const withdrawals = ref([])
const ledger = ref([])

function wText(s) { return s === 'paid' ? '已打款' : s === 'rejected' ? '已驳回' : '待审核' }

async function load() {
  withdrawals.value = (await request.get('/admin/withdrawals')).map((w) => ({
    id: w.id, doctor: w.doctor, amount: w.amount, time: w.created_at || '', status: wText(w.status)
  }))
  ledger.value = (await request.get('/finance/ledger')).map((l) => ({
    order: l.order_id, total: l.total, hospital: l.hospital, doctor: l.doctor, platform: l.platform
  }))
}
onMounted(load)

// 审核通过 → 调微信「商家转账到零钱」打款
function approve(row) {
  ElMessageBox.confirm(`确认向 ${row.doctor} 打款 ¥${row.amount}？`, '提现审批', { type: 'warning' })
    .then(async () => {
      await request.post(`/admin/withdrawals/${row.id}/audit`, { approve: true })
      ElMessage.success('已调用微信商家转账'); load()
    }).catch(() => {})
}
async function reject(row) {
  await request.post(`/admin/withdrawals/${row.id}/audit`, { approve: false })
  ElMessage.warning('已驳回提现，解冻余额'); load()
}
</script>

<template>
  <el-card>
    <template #header>提现审批（医生发起 → 冻结 → 人工审核 → 商家转账到零钱）</template>
    <el-table :data="withdrawals">
      <el-table-column prop="id" label="提现单号" width="120" />
      <el-table-column prop="doctor" label="医生" width="120" />
      <el-table-column prop="amount" label="金额(元)" width="140" />
      <el-table-column prop="time" label="申请时间" width="200" />
      <el-table-column prop="status" label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="row.status === '已打款' ? 'success' : row.status === '已驳回' ? 'danger' : 'info'">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button size="small" type="success" @click="approve(row)" :disabled="row.status !== '待审核'">通过打款</el-button>
          <el-button size="small" type="danger" @click="reject(row)" :disabled="row.status !== '待审核'">驳回</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-card class="mt">
    <template #header>分账流水（每单自动拆分：医院留存 / 医生分成 / 平台技术服务费）</template>
    <el-table :data="ledger">
      <el-table-column prop="order" label="订单号" />
      <el-table-column prop="total" label="总金额" />
      <el-table-column prop="hospital" label="医院留存" />
      <el-table-column prop="doctor" label="医生分成" />
      <el-table-column prop="platform" label="平台服务费" />
    </el-table>
  </el-card>
</template>

<style scoped>
.mt { margin-top: 16px; }
</style>
