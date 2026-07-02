<script setup>
import { ref, onMounted } from 'vue'
import request from '@/api/request'

// 患者评价（只读）：天津监管 2.4.1 uploadBusinessInfoAfter 的数据源
const list = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try { list.value = await request.get('/admin/evaluations') || [] }
  finally { loading.value = false }
}
onMounted(load)

const SATISFACTION = { 1: '非常不满意', 2: '不满意', 3: '一般', 4: '满意', 5: '非常满意' }
function satType(v) { return v >= 4 ? 'success' : v === 3 ? 'warning' : 'danger' }
function typeLabel(t) { return t === 'text' ? '图文咨询' : '视频复诊' }
</script>

<template>
  <el-card>
    <template #header>
      <div class="hd"><span>患者评价（随每日批次上报监管平台，评价由患者在小程序提交）</span></div>
    </template>
    <el-table :data="list" v-loading="loading">
      <el-table-column prop="created_at" label="评价时间" width="150" />
      <el-table-column prop="order_no" label="订单号" width="200" show-overflow-tooltip />
      <el-table-column label="业务" width="100">
        <template #default="{ row }"><el-tag>{{ typeLabel(row.consult_type) }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="doctor_name" label="医生" width="100" />
      <el-table-column label="满意度" width="110">
        <template #default="{ row }">
          <el-tag :type="satType(row.satisfaction)">{{ SATISFACTION[row.satisfaction] || row.satisfaction }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="评分" width="120">
        <template #default="{ row }"><el-rate :model-value="row.scoring / 2" disabled allow-half /> </template>
      </el-table-column>
      <el-table-column prop="content" label="评价内容" show-overflow-tooltip />
      <el-table-column prop="complaints" label="投诉建议" show-overflow-tooltip />
      <el-table-column prop="evaluator" label="评价人" width="90" />
    </el-table>
  </el-card>
</template>

<style scoped>
.hd { display: flex; align-items: center; justify-content: space-between; }
</style>
