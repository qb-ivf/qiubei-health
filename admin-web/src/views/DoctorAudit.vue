<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/api/request'

// 医生入驻 / 多点执业资质终审（PRD §4.1）
const list = ref([])

function statusText(s) {
  return s === 'approved' ? '已通过' : s === 'rejected' ? '已驳回' : '待审核'
}

async function load() {
  const data = await request.get('/admin/doctors')
  list.value = (data || []).map((d) => ({
    id: d.id, name: d.name || '(未填)', idcard: '—', dept: d.dept, title: d.title,
    license: d.license_no || '—', practice: d.practice_no || '—', status: statusText(d.audit_status)
  }))
}
onMounted(load)

async function pass(row) {
  await request.post(`/admin/doctors/${row.id}/audit`, { approve: true })
  ElMessage.success(`${row.name} 资质审核通过`); load()
}
async function deny(row) {
  await request.post(`/admin/doctors/${row.id}/audit`, { approve: false })
  ElMessage.warning(`${row.name} 资质被驳回`); load()
}
function preview() { ElMessage.info('查看高清资质照片（OSS 防盗链访问）') }
</script>

<template>
  <el-card>
    <template #header>医生资质终审</template>
    <el-table :data="list">
      <el-table-column prop="name" label="姓名" width="100" />
      <el-table-column prop="idcard" label="身份证(脱敏)" width="180" />
      <el-table-column prop="dept" label="科室" width="120" />
      <el-table-column prop="title" label="职称" width="120" />
      <el-table-column prop="license" label="资格证" />
      <el-table-column prop="practice" label="执业证" />
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === '已通过' ? 'success' : row.status === '已驳回' ? 'danger' : 'info'">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240">
        <template #default="{ row }">
          <el-button size="small" @click="preview">查看证件</el-button>
          <el-button size="small" type="success" @click="pass(row)">通过</el-button>
          <el-button size="small" type="danger" @click="deny(row)">驳回</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>
