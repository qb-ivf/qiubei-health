<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

// 院内药房与药品字典（PRD §4.2：特殊限售药强制拦截）
const list = ref([
  { id: 1, name: '阿莫西林胶囊', spec: '0.25g*24粒', type: '处方药', price: 18.5, restricted: false },
  { id: 2, name: '布洛芬缓释胶囊', spec: '0.3g*22粒', type: '非处方药', price: 21.0, restricted: false },
  { id: 3, name: '盐酸哌替啶注射液', spec: '50mg', type: '特殊限售药', price: 0, restricted: true }
])

function tagType(t) {
  return t === '特殊限售药' ? 'danger' : t === '处方药' ? 'warning' : 'success'
}
function toggle(row) {
  if (row.restricted) {
    ElMessage.error('合规限制：麻醉/精神/放射性等特殊药品禁止上架（互联网医院严禁开具）')
    return
  }
  ElMessage.success(`已更新 ${row.name}`)
}
</script>

<template>
  <el-card>
    <template #header>药品字典（特殊限售药强制标记并拦截）</template>
    <el-table :data="list">
      <el-table-column prop="name" label="药品名称" />
      <el-table-column prop="spec" label="规格" width="160" />
      <el-table-column prop="type" label="属性" width="140">
        <template #default="{ row }"><el-tag :type="tagType(row.type)">{{ row.type }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="price" label="单价(元)" width="120" />
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button size="small" :type="row.restricted ? 'danger' : 'primary'" @click="toggle(row)">
            {{ row.restricted ? '禁止上架' : '编辑' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>
