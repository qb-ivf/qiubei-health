<script setup>
import { reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import request from '@/api/request'

const router = useRouter()
const form = reactive({ username: '', password: '' })

async function login() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入账号和密码')
    return
  }
  try {
    // 真实 RBAC：后端校验 staff 账号密码，角色以库为准
    const res = await request.post('/auth/admin/login', {
      username: form.username, password: form.password
    })
    localStorage.setItem('token', res.token)
    localStorage.setItem('role', res.role)
    router.replace('/dashboard')
  } catch (e) { /* 拦截器已提示 */ }
}
</script>

<template>
  <div class="login">
    <el-card class="login__card">
      <div class="login__title">逑贝互联网医院 · 运营管理后台</div>
      <el-form :model="form" label-position="top" @submit.prevent>
        <el-form-item label="账号">
          <el-input v-model="form.username" placeholder="管理员 / 药师 / 财务账号" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" />
        </el-form-item>
        <el-button type="primary" class="login__btn" @click="login">登 录</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login { height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #0056c4, #1d6fec); }
.login__card { width: 380px; }
.login__title { font-size: 18px; font-weight: 700; text-align: center; margin-bottom: 20px; color: #0056c4; }
.login__btn { width: 100%; }
</style>
