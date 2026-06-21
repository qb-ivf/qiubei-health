<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

// 医生入驻 / 多点执业资质终审（PRD §4.1）
const list = ref([
  { id: 1, name: '张建设', idcard: '120***********1234', dept: '呼吸内科', title: '主任医师',
    license: '医师资格证 1101xxxx', practice: '执业证 2201xxxx（多点执业）', status: '待审核' },
  { id: 2, name: '王美丽', idcard: '120***********5678', dept: '呼吸内科', title: '副主任医师',
    license: '医师资格证 1102xxxx', practice: '执业证 2202xxxx', status: '待审核' }
])

function pass(row) { row.status = '已通过'; ElMessage.success(`${row.name} 资质审核通过`) }
function deny(row) { row.status = '已驳回'; ElMessage.warning(`${row.name} 资质被驳回`) }
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
