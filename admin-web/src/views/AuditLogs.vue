<script setup>
import { ref, onMounted } from 'vue'
import request from '@/api/request'

// 操作审计日志查询
const list = ref([])
const loading = ref(false)
const action = ref('')
const actor = ref('')

const ACTIONS = ['', '审方通过', '审方驳回', '资质终审通过', '资质终审驳回', '提现打款', '提现驳回',
  '新增药品', '编辑药品', '删除药品', '创建账号', '编辑账号', '重置密码', '删除账号']

const ROLE_TEXT = { admin: '管理员', pharmacist: '药师', finance: '财务' }

async function load() {
  loading.value = true
  try {
    const params = []
    if (action.value) params.push(`action=${encodeURIComponent(action.value)}`)
    if (actor.value) params.push(`actor=${encodeURIComponent(actor.value)}`)
    const q = params.length ? `?${params.join('&')}` : ''
    list.value = (await request.get(`/admin/audit-logs${q}`)) || []
  } finally {
    loading.value = false
  }
}
onMounted(load)
function reset() { action.value = ''; actor.value = ''; load() }
</script>

<template>
  <el-card>
    <template #header>
      <div class="hd">
        <span>操作审计日志（医疗/资金/资质/账号 写操作留痕）</span>
        <div class="filters">
          <el-select v-model="action" placeholder="动作" style="width: 140px" @change="load">
            <el-option v-for="a in ACTIONS" :key="a" :label="a || '全部动作'" :value="a" />
          </el-select>
          <el-input v-model="actor" placeholder="操作人" style="width: 140px" clearable @keyup.enter="load" />
          <el-button type="primary" @click="load">查询</el-button>
          <el-button @click="reset">重置</el-button>
        </div>
      </div>
    </template>
    <el-table :data="list" v-loading="loading">
      <el-table-column prop="id" label="#" width="70" />
      <el-table-column prop="created_at" label="时间" width="150" />
      <el-table-column label="操作人" width="160">
        <template #default="{ row }">{{ row.actor_name || '—' }}<el-tag size="small" class="ml" v-if="row.actor_role">{{ ROLE_TEXT[row.actor_role] || row.actor_role }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="action" label="动作" width="130">
        <template #default="{ row }"><el-tag type="warning">{{ row.action }}</el-tag></template>
      </el-table-column>
      <el-table-column label="对象" width="160">
        <template #default="{ row }">{{ row.target_type || '' }}{{ row.target_id ? ' #' + row.target_id : '' }}</template>
      </el-table-column>
      <el-table-column prop="detail" label="详情" min-width="200" />
      <el-table-column prop="ip" label="IP" width="140" />
    </el-table>
  </el-card>
</template>

<style scoped>
.hd { display: flex; align-items: center; justify-content: space-between; }
.filters { display: flex; gap: 8px; }
.ml { margin-left: 6px; }
</style>
