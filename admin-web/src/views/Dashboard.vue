<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

// 监管数据上报监控面板（PRD §4.4）
const stats = ref([
  { label: '今日上报总数', value: 1284, color: '#0056c4' },
  { label: '上报成功', value: 1271, color: '#00b578' },
  { label: '上报失败', value: 13, color: '#fa5151' },
  { label: '平均延迟', value: '420ms', color: '#894d00' }
])

const failed = ref([
  { id: 'RPT20260621001', type: '开药明细', time: '2026-06-21 14:02', err: '卫健委网关 502' },
  { id: 'RPT20260621002', type: '问诊记录', time: '2026-06-21 13:48', err: '响应超时' }
])

function retry(row) {
  // 调 /api/v1/compliance/retry，重新投递死信队列任务
  ElMessage.success(`已重新上报 ${row.id}`)
  failed.value = failed.value.filter((r) => r.id !== row.id)
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
