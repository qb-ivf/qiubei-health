<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/api/request'

// 监管数据上报监控面板（PRD §4.4 / M9）
const stats = ref([])
const failed = ref([])

const TYPE_TEXT = { consultation: '问诊记录', prescription: '开药明细' }

async function load() {
  const s = await request.get('/admin/gov-reports/stats')
  stats.value = [
    { label: '上报总数', value: s.total, color: '#0056c4' },
    { label: '上报成功', value: s.success, color: '#00b578' },
    { label: '上报失败', value: s.failed, color: '#fa5151' },
    { label: '平均延迟', value: s.avg_ms + 'ms', color: '#894d00' }
  ]
  const f = await request.get('/admin/gov-reports/failed')
  failed.value = f.map((r) => ({
    id: r.id, type: TYPE_TEXT[r.type] || r.type, time: `重试 ${r.retries} 次`, err: r.err || r.status
  }))
}
onMounted(load)

async function retry(row) {
  await request.post(`/admin/gov-reports/${row.id}/retry`)
  ElMessage.success(`已重新投递上报 #${row.id}`)
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
    <template #header>失败任务（支持一键重新上报）</template>
    <el-table :data="failed">
      <el-table-column prop="id" label="上报编号" width="200" />
      <el-table-column prop="type" label="数据类型" />
      <el-table-column prop="time" label="时间" width="200" />
      <el-table-column prop="err" label="失败原因" />
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="retry(row)">重新上报</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<style scoped>
.stat__label { color: #909399; font-size: 13px; }
.stat__value { font-size: 28px; font-weight: 700; margin-top: 8px; }
.mt { margin-top: 16px; }
</style>
