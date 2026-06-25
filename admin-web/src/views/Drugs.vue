<script setup>
import { ref, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/api/request'

// 院内药房与药品字典（PRD §4.2：特殊限售药强制拦截）
const list = ref([])
const loading = ref(false)
const dialog = ref(false)
const editing = ref(null)   // null=新增，否则=药品id
const CATEGORIES = ['处方药', '非处方药', '特殊限售药']
const form = reactive({ name: '', spec: '', price: 0, category: '处方药', restricted: false })

async function load() {
  loading.value = true
  try {
    const data = await request.get('/admin/drugs')
    list.value = (data || []).map((d) => ({
      id: d.id, name: d.name, spec: d.spec, category: d.category, price: d.price, restricted: d.restricted
    }))
  } finally {
    loading.value = false
  }
}
onMounted(load)

function tagType(t) {
  return t === '特殊限售药' ? 'danger' : t === '处方药' ? 'warning' : 'success'
}

function openAdd() {
  editing.value = null
  Object.assign(form, { name: '', spec: '', price: 0, category: '处方药', restricted: false })
  dialog.value = true
}
function openEdit(row) {
  editing.value = row.id
  Object.assign(form, { name: row.name, spec: row.spec || '', price: row.price, category: row.category, restricted: row.restricted })
  dialog.value = true
}

// 特殊限售药 → 自动标记 restricted（开方时后端拦截）
function onCategory(v) { if (v === '特殊限售药') form.restricted = true }

async function save() {
  if (!form.name) { ElMessage.warning('请输入药品名称'); return }
  const payload = { name: form.name, spec: form.spec, price: Number(form.price), category: form.category, restricted: form.restricted }
  if (editing.value) {
    await request.put(`/admin/drugs/${editing.value}`, payload)
    ElMessage.success('已更新')
  } else {
    await request.post('/admin/drugs', payload)
    ElMessage.success('已新增')
  }
  dialog.value = false
  load()
}

function remove(row) {
  ElMessageBox.confirm(`确认删除药品「${row.name}」？`, '删除药品', { type: 'warning' })
    .then(async () => {
      await request.delete(`/admin/drugs/${row.id}`)
      ElMessage.success('已删除'); load()
    }).catch(() => {})
}
</script>

<template>
  <el-card>
    <template #header>
      <div class="hd">
        <span>药品字典（特殊限售药强制标记，开方时后端拦截）</span>
        <el-button type="primary" @click="openAdd">新增药品</el-button>
      </div>
    </template>
    <el-table :data="list" v-loading="loading">
      <el-table-column prop="name" label="药品名称" />
      <el-table-column prop="spec" label="规格" width="160" />
      <el-table-column prop="category" label="属性" width="140">
        <template #default="{ row }"><el-tag :type="tagType(row.category)">{{ row.category }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="price" label="单价(元)" width="120" />
      <el-table-column label="限售拦截" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.restricted" type="danger" effect="dark">已拦截</el-tag>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="dialog" :title="editing ? '编辑药品' : '新增药品'" width="460px">
    <el-form :model="form" label-width="90px">
      <el-form-item label="药品名称"><el-input v-model="form.name" placeholder="如 阿莫西林胶囊" /></el-form-item>
      <el-form-item label="规格"><el-input v-model="form.spec" placeholder="如 0.25g*24粒" /></el-form-item>
      <el-form-item label="单价(元)"><el-input-number v-model="form.price" :min="0" :precision="2" :step="1" /></el-form-item>
      <el-form-item label="属性">
        <el-select v-model="form.category" @change="onCategory">
          <el-option v-for="c in CATEGORIES" :key="c" :label="c" :value="c" />
        </el-select>
      </el-form-item>
      <el-form-item label="限售拦截">
        <el-switch v-model="form.restricted" />
        <span class="hint">开启后，医生开方搜索该药将被后端直接拦截</span>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialog = false">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.hd { display: flex; align-items: center; justify-content: space-between; }
.muted { color: #c0c4cc; }
.hint { color: #909399; font-size: 12px; margin-left: 10px; }
</style>
