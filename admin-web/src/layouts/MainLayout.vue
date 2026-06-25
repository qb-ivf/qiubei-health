<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
const route = useRoute()
const router = useRouter()

const ROLE_TEXT = { admin: '管理员', pharmacist: '审方药师', finance: '财务' }
const role = localStorage.getItem('role')

const ALL_MENUS = [
  { path: '/overview', title: '运营概览', icon: 'DataAnalysis', roles: ['admin'] },
  { path: '/orders', title: '订单管理', icon: 'List', roles: ['admin', 'finance'] },
  { path: '/pharmacist', title: '药师审方', icon: 'DocumentChecked', roles: ['admin', 'pharmacist'] },
  { path: '/doctor-audit', title: '医生资质终审', icon: 'Postcard', roles: ['admin'] },
  { path: '/drugs', title: '药品字典', icon: 'FirstAidKit', roles: ['admin', 'pharmacist'] },
  { path: '/finance', title: '财务对账提现', icon: 'Money', roles: ['admin', 'finance'] },
  { path: '/dashboard', title: '监管上报面板', icon: 'DataLine', roles: ['admin'] },
  { path: '/audit-logs', title: '操作审计', icon: 'Tickets', roles: ['admin'] },
  { path: '/staff', title: '账号管理', icon: 'UserFilled', roles: ['admin'] }
]
const menus = computed(() => ALL_MENUS.filter((m) => m.roles.includes(role)))

function logout() {
  localStorage.removeItem('token')
  localStorage.removeItem('role')
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
        <div class="header__right">
          <el-tag size="small" effect="plain">{{ ROLE_TEXT[role] || role }}</el-tag>
          <el-button text type="primary" @click="logout">退出登录</el-button>
        </div>
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
.header__right { display: flex; align-items: center; gap: 12px; }
</style>
