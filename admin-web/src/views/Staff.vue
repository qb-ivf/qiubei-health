<script setup>
import { ref, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/api/request'

// 运营账号管理（RBAC：admin/pharmacist/finance）
const list = ref([])
const loading = ref(false)
const dialog = ref(false)
const editing = ref(null)
const ROLES = [
  { v: 'admin', t: '管理员' }, { v: 'pharmacist', t: '审方药师' }, { v: 'finance', t: '财务' }
]
const ROLE_TEXT = { admin: '管理员', pharmacist: '审方药师', finance: '财务' }
const form = reactive({ username: '', password: '', name: '', role: 'pharmacist' })

async function load() {
  loading.value = true
  try {
    list.value = (await request.get('/admin/staff')) || []
  } finally {
    loading.value = false
  }
}
onMounted(load)

function openAdd() {
  editing.value = null
  Object.assign(form, { username: '', password: '', name: '', role: 'pharmacist' })
  dialog.value = true
}
function openEdit(row) {
  editing.value = row.id
  Object.assign(form, { username: row.username, password: '', name: row.name || '', role: row.role })
  dialog.value = true
}

async function save() {
  if (!editing.value && (!form.username || !form.password)) { ElMessage.warning('请输入用户名和密码'); return }
  if (editing.value) {
    await request.put(`/admin/staff/${editing.value}`, { name: form.name, role: form.role })
    ElMessage.success('已保存')
  } else {
    await request.post('/admin/staff', { username: form.username, password: form.password, name: form.name, role: form.role })
    ElMessage.success('已创建')
  }
  dialog.value = false
  load()
}

function resetPwd(row) {
  ElMessageBox.prompt(`为账号「${row.username}」设置新密码`, '重置密码', {
    confirmButtonText: '确认', cancelButtonText: '取消', inputType: 'password',
    inputValidator: (v) => (v && v.length >= 6 ? true : '密码至少 6 位')
  }).then(async ({ value }) => {
    await request.post(`/admin/staff/${row.id}/reset-password`, { password: value })
    ElMessage.success('密码已重置')
  }).catch(() => {})
}

async function toggleActive(row) {
  await request.put(`/admin/staff/${row.id}`, { active: !row.active })
  ElMessage.success(row.active ? '已停用' : '已启用')
  load()
}

function remove(row) {
  ElMessageBox.confirm(`确认删除账号「${row.username}」？`, '删除账号', { type: 'warning' })
    .then(async () => {
      await request.delete(`/admin/staff/${row.id}`)
      ElMessage.success('已删除'); load()
    }).catch(() => {})
}
</script>

<template>
  <el-card>
    <template #header>
      <div class="hd">
        <span>运营账号管理（角色决定可见菜单与操作权限）</span>
        <el-button type="primary" @click="openAdd">新增账号</el-button>
      </div>
    </template>
    <el-table :data="list" v-loading="loading">
      <el-table-column prop="id" label="#" width="70" />
      <el-table-column prop="username" label="用户名" width="160" />
      <el-table-column prop="name" label="姓名" width="140" />
      <el-table-column label="角色" width="120">
        <template #default="{ row }"><el-tag :type="row.role === 'admin' ? 'danger' : row.role === 'finance' ? 'warning' : 'success'">{{ ROLE_TEXT[row.role] || row.role }}</el-tag></template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }"><el-tag :type="row.active ? 'success' : 'info'">{{ row.active ? '启用' : '停用' }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="150" />
      <el-table-column label="操作" width="300">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="warning" @click="resetPwd(row)">重置密码</el-button>
          <el-button size="small" @click="toggleActive(row)">{{ row.active ? '停用' : '启用' }}</el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="dialog" :title="editing ? '编辑账号' : '新增账号'" width="440px">
    <el-form :model="form" label-width="80px">
      <el-form-item label="用户名"><el-input v-model="form.username" :disabled="!!editing" placeholder="登录用户名" /></el-form-item>
      <el-form-item v-if="!editing" label="密码"><el-input v-model="form.password" type="password" placeholder="至少 6 位" /></el-form-item>
      <el-form-item label="姓名"><el-input v-model="form.name" placeholder="真实姓名（可选）" /></el-form-item>
      <el-form-item label="角色">
        <el-select v-model="form.role">
          <el-option v-for="r in ROLES" :key="r.v" :label="r.t" :value="r.v" />
        </el-select>
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
</style>
