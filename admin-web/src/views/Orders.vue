<script setup>
import { ref, onMounted } from 'vue'
import request from '@/api/request'

// 订单管理（全部问诊订单可查）
const list = ref([])
const loading = ref(false)
const status = ref('')

const STATUS_OPTS = [
  { v: '', t: '全部' }, { v: 0, t: '待支付' }, { v: 1, t: '候诊中' }, { v: 2, t: '问诊中' },
  { v: 3, t: '待审方' }, { v: 4, t: '审方驳回' }, { v: 5, t: '已开方' }, { v: 6, t: '已完成' },
  { v: 7, t: '已退款' }, { v: 9, t: '已取消' }
]
const STATUS_TAG = {
  待支付: 'info', 候诊中: 'warning', 问诊中: '', 待审方: 'warning', 审方驳回: 'danger',
  已开方: 'success', 已完成: 'success', 已退款: 'danger', 已取消: 'info'
}

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
      <el-table-column prop="drug_fee" label="药费(元)" width="100" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="STATUS_TAG[row.status_text]">{{ row.status_text }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="下单时间" width="150" />
    </el-table>
  </el-card>
</template>

<style scoped>
.hd { display: flex; align-items: center; justify-content: space-between; }
</style>
