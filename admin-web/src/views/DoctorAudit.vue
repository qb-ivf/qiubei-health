<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/api/request'

// 医生入驻 / 多点执业资质终审（PRD §4.1）
const tab = ref('pending')
const list = ref([])
const loading = ref(false)
const drawer = ref(false)
const current = ref({})

const TABS = [
  { k: 'pending', t: '待审核' },
  { k: 'approved', t: '已通过' },
  { k: 'rejected', t: '已驳回' },
  { k: 'all', t: '全部' }
]
const STATUS = {
  pending: { t: '待审核', type: 'info' },
  approved: { t: '已通过', type: 'success' },
  rejected: { t: '已驳回', type: 'danger' }
}

async function load() {
  loading.value = true
  try {
    const q = tab.value === 'all' ? '' : `?status=${tab.value}`
    const data = await request.get(`/admin/doctors${q}`)
    list.value = (data || []).map((d) => ({
      id: d.id, name: d.name || '(未填)', dept: d.dept || '—', title: d.title || '—',
      license: d.license_no || '—', practice: d.practice_no || '—',
      phone: d.phone || '—', goodAt: d.good_at || '—', years: d.years, fee: d.register_fee,
      status: d.audit_status, time: d.created_at
    }))
  } finally {
    loading.value = false
  }
}
onMounted(load)
function switchTab(k) { tab.value = k; load() }

function detail(row) { current.value = row; drawer.value = true }

async function pass(row) {
  await request.post(`/admin/doctors/${row.id}/audit`, { approve: true })
  ElMessage.success(`${row.name} 资质审核通过`); drawer.value = false; load()
}
async function deny(row) {
  await request.post(`/admin/doctors/${row.id}/audit`, { approve: false })
  ElMessage.warning(`${row.name} 资质被驳回`); drawer.value = false; load()
}
</script>

<template>
  <el-card>
    <template #header>
      <div class="hd">
        <span>医生资质终审</span>
        <el-radio-group :model-value="tab" @change="switchTab">
          <el-radio-button v-for="t in TABS" :key="t.k" :value="t.k">{{ t.t }}</el-radio-button>
        </el-radio-group>
      </div>
    </template>
    <el-table :data="list" v-loading="loading">
      <el-table-column prop="name" label="姓名" width="100" />
      <el-table-column prop="phone" label="手机号(脱敏)" width="140" />
      <el-table-column prop="dept" label="科室" width="110" />
      <el-table-column prop="title" label="职称" width="110" />
      <el-table-column prop="license" label="资格证" />
      <el-table-column prop="practice" label="执业证" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="(STATUS[row.status] || {}).type">{{ (STATUS[row.status] || {}).t || row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240">
        <template #default="{ row }">
          <el-button size="small" @click="detail(row)">查看详情</el-button>
          <el-button size="small" type="success" :disabled="row.status === 'approved'" @click="pass(row)">通过</el-button>
          <el-button size="small" type="danger" :disabled="row.status === 'rejected'" @click="deny(row)">驳回</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-drawer v-model="drawer" :title="`医生资质 · ${current.name}`" size="420px">
    <el-descriptions :column="1" border>
      <el-descriptions-item label="姓名">{{ current.name }}</el-descriptions-item>
      <el-descriptions-item label="手机号">{{ current.phone }}</el-descriptions-item>
      <el-descriptions-item label="科室">{{ current.dept }}</el-descriptions-item>
      <el-descriptions-item label="职称">{{ current.title }}</el-descriptions-item>
      <el-descriptions-item label="执业医师资格证号">{{ current.license }}</el-descriptions-item>
      <el-descriptions-item label="医师执业证号">{{ current.practice }}</el-descriptions-item>
      <el-descriptions-item label="擅长">{{ current.goodAt }}</el-descriptions-item>
      <el-descriptions-item label="执业年限">{{ current.years || '—' }} 年</el-descriptions-item>
      <el-descriptions-item label="挂号费">¥{{ current.fee }}</el-descriptions-item>
      <el-descriptions-item label="提交时间">{{ current.time }}</el-descriptions-item>
      <el-descriptions-item label="当前状态">
        <el-tag :type="(STATUS[current.status] || {}).type">{{ (STATUS[current.status] || {}).t || current.status }}</el-tag>
      </el-descriptions-item>
    </el-descriptions>
    <div class="drawer-foot">
      <el-button type="success" :disabled="current.status === 'approved'" @click="pass(current)">通过终审</el-button>
      <el-button type="danger" :disabled="current.status === 'rejected'" @click="deny(current)">驳回</el-button>
    </div>
  </el-drawer>
</template>

<style scoped>
.hd { display: flex; align-items: center; justify-content: space-between; }
.drawer-foot { margin-top: 20px; display: flex; gap: 12px; }
</style>
