<script setup>
import { useRoute, useRouter } from 'vue-router'
const route = useRoute()
const router = useRouter()

const menus = [
  { path: '/dashboard', title: '监管上报面板', icon: 'DataLine' },
  { path: '/orders', title: '订单管理', icon: 'List' },
  { path: '/pharmacist', title: '药师审方', icon: 'DocumentChecked' },
  { path: '/doctor-audit', title: '医生资质终审', icon: 'Postcard' },
  { path: '/drugs', title: '药品字典', icon: 'FirstAidKit' },
  { path: '/finance', title: '财务对账提现', icon: 'Money' }
]

function logout() {
  localStorage.removeItem('token')
  router.replace('/login')
}
</script>

<template>
  <el-container class="app">
    <el-aside width="220px" class="aside">
      <div class="brand">逑贝运营后台</div>
      <el-menu :default-active="route.path" router background-color="#001b3d" text-color="#c2c6d7" active-text-color="#fff">
        <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon>
          <span>{{ m.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="header__title">{{ route.name }}</span>
        <el-button text type="primary" @click="logout">退出登录</el-button>
      </el-header>
      <el-main><router-view /></el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.app { height: 100vh; }
.aside { background: #001b3d; }
.brand { color: #fff; font-size: 18px; font-weight: 700; padding: 18px 20px; letter-spacing: 1px; }
.header { display: flex; align-items: center; justify-content: space-between; background: #fff; border-bottom: 1px solid #e4e7ed; }
.header__title { font-size: 16px; font-weight: 600; }
</style>
