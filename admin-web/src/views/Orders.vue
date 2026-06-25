<script setup>
import { ref, onMounted } from 'vue'
import request from '@/api/request'

// 订单管理（全部问诊订单 + 详情）
const list = ref([])
const loading = ref(false)
const status = ref('')
const drawer = ref(false)
const detail = ref({})
const detailLoading = ref(false)

const STATUS_OPTS = [
  { v: '', t: '全部' }, { v: 0, t: '待支付' }, { v: 1, t: '候诊中' }, { v: 2, t: '问诊中' },
  { v: 3, t: '待审方' }, { v: 4, t: '审方驳回' }, { v: 5, t: '已开方' }, { v: 6, t: '已完成' },
  { v: 7, t: '已退款' }, { v: 9, t: '已取消' }
]
const STATUS_TAG = {
  待支付: 'info', 候诊中: 'warning', 问诊中: '', 待审方: 'warning', 审方驳回: 'danger',
  已开方: 'success', 已完成: 'success', 已退款: 'danger', 已取消: 'info'
}
const RX_STATUS = { pending: { t: '待审核', type: 'info' }, approved: { t: '已通过', type: 'success' }, rejected: { t: '已驳回', type: 'danger' } }

async function load() {
  loading.value = true
  try {
    const q = status.value === '' ? '' : `?status=${status.value}`
    list.value = (await request.get(`/admin/orders${q}`)) || []
  } finally {
    loading.value = false
  }
}
onMounted(load)
function onChange() { load() }

async function openDetail(row) {
  drawer.value = true
  detailLoading.value = true
  detail.value = {}
  try {
    detail.value = await request.get(`/admin/orders/${row.id}`)
  } finally {
    detailLoading.value = false
  }
}
</script>

<template>
  <el-card>
    <template #header>
      <div class="hd">
        <span>订单管理（全部问诊订单）</span>
        <el-select v-model="status" style="width: 140px" @change="onChange">
          <el-option v-for="o in STATUS_OPTS" :key="o.v" :label="o.t" :value="o.v" />
        </el-select>
      </div>
    </template>
    <el-table :data="list" v-loading="loading">
      <el-table-column prop="order_no" label="订单号" min-width="170" />
      <el-table-column prop="patient_name" label="患者" width="90" />
      <el-table-column prop="doctor_name" label="医生" width="100" />
      <el-table-column prop="type" label="类型" width="80" />
      <el-table-column prop="register_fee" label="挂号费(元)" width="100" />
      <el-table-column prop="drug_fee" label="药费(元)" width="90" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="STATUS_TAG[row.status_text]">{{ row.status_text }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="下单时间" width="150" />
      <el-table-column label="操作" width="90">
        <template #default="{ row }"><el-button size="small" @click="openDetail(row)">详情</el-button></template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-drawer v-model="drawer" :title="`订单详情 · ${detail.order_no || ''}`" size="500px">
    <div v-loading="detailLoading">
      <el-descriptions title="订单信息" :column="1" border>
        <el-descriptions-item label="订单号">{{ detail.order_no }}</el-descriptions-item>
        <el-descriptions-item label="类型">{{ detail.type }}</el-descriptions-item>
        <el-descriptions-item label="状态"><el-tag :type="STATUS_TAG[detail.status_text]">{{ detail.status_text }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="患者">{{ detail.patient_name }}</el-descriptions-item>
        <el-descriptions-item label="医生">{{ detail.doctor_name }} <span v-if="detail.dept" class="muted">/ {{ detail.dept }}</span></el-descriptions-item>
        <el-descriptions-item label="挂号费">¥{{ detail.register_fee }}</el-descriptions-item>
        <el-descriptions-item label="药费">¥{{ detail.drug_fee }}</el-descriptions-item>
        <el-descriptions-item label="合计">¥{{ detail.total_fee }}</el-descriptions-item>
        <el-descriptions-item label="下单时间">{{ detail.created_at }}</el-descriptions-item>
        <el-descriptions-item label="最近更新">{{ detail.updated_at }}</el-descriptions-item>
      </el-descriptions>

      <template v-if="detail.prescription">
        <el-descriptions title="处方信息" :column="1" border class="mt">
          <el-descriptions-item label="审核状态">
            <el-tag :type="(RX_STATUS[detail.prescription.audit_status] || {}).type">{{ (RX_STATUS[detail.prescription.audit_status] || {}).t || detail.prescription.audit_status }}</el-tag>
            <span v-if="detail.prescription.reject_reason" class="reason">驳回：{{ detail.prescription.reject_reason }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="主诉">{{ detail.prescription.chief || '—' }}</el-descriptions-item>
          <el-descriptions-item label="现病史">{{ detail.prescription.present_illness || '—' }}</el-descriptions-item>
          <el-descriptions-item label="临床诊断">{{ detail.prescription.diagnosis || '—' }}</el-descriptions-item>
          <el-descriptions-item label="医嘱">{{ detail.prescription.advice || '—' }}</el-descriptions-item>
        </el-descriptions>
        <el-table :data="detail.prescription.items" class="mt" size="small" border>
          <el-table-column prop="name" label="药品" />
          <el-table-column prop="spec" label="规格" width="110" />
          <el-table-column prop="qty" label="数量" width="60" />
          <el-table-column prop="usage" label="用法" min-width="120" />
        </el-table>
      </template>
      <el-empty v-else description="该订单暂无处方" :image-size="60" class="mt" />
    </div>
  </el-drawer>
</template>

<style scoped>
.hd { display: flex; align-items: center; justify-content: space-between; }
.mt { margin-top: 18px; }
.muted { color: #909399; }
.reason { color: #fa5151; margin-left: 10px; }
</style>
