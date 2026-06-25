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
    router.replace('/')
  } catch (e) { /* 拦截器已提示 */ }
}
</script>

<template>
  <div class="login">
    <div class="login__brand">
      <img src="/logo.png" class="login__logo" alt="logo" />
      <div class="login__brandtxt">
        <div class="login__name">逑贝医疗</div>
        <div class="login__en">QBIVF MEDICAL · 互联网医院</div>
      </div>
    </div>
    <el-card class="login__card">
      <div class="login__title">运营管理后台</div>
      <div class="login__sub">请使用管理员 / 药师 / 财务账号登录</div>
      <el-form :model="form" label-position="top" @submit.prevent>
        <el-form-item label="账号">
          <el-input v-model="form.username" size="large" placeholder="登录账号" :prefix-icon="'User'" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" size="large" type="password" show-password placeholder="请输入密码" :prefix-icon="'Lock'" @keyup.enter="login" />
        </el-form-item>
        <el-button type="primary" size="large" class="login__btn" @click="login">登 录</el-button>
      </el-form>
    </el-card>
    <div class="login__foot">© 逑贝医疗 · 天津逑贝互联网医院</div>
  </div>
</template>

<style scoped>
.login {
  height: 100vh; display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 22px;
}
.login__brand { display: flex; align-items: center; gap: 14px; }
.login__logo { width: 60px; height: 60px; background: #fff; border-radius: 14px; padding: 7px; box-sizing: border-box; box-shadow: 0 6px 20px rgba(0, 0, 0, .15); }
.login__brandtxt { color: #fff; }
.login__name { font-size: 30px; font-weight: 800; letter-spacing: 3px; line-height: 1.1; }
.login__en { font-size: 12px; opacity: .9; letter-spacing: 1.5px; margin-top: 4px; }
.login__card { width: 380px; border-radius: 16px; box-shadow: 0 12px 40px rgba(0, 0, 0, .18); }
.login__title { font-size: 19px; font-weight: 700; text-align: center; color: var(--brand-blue); }
.login__sub { font-size: 12px; color: var(--el-text-color-secondary); text-align: center; margin: 6px 0 18px; }
.login__btn { width: 100%; font-weight: 600; letter-spacing: 4px; }
.login__foot { color: rgba(255, 255, 255, .85); font-size: 12px; letter-spacing: .5px; }
</style>
