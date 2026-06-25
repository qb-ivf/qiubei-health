<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Moon, Sunny } from '@element-plus/icons-vue'
import { isDark, toggleTheme } from '@/composables/theme'
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
    <el-aside width="224px" class="app-aside">
      <div class="app-brand">
        <img src="/logo.png" class="app-brand__logo" alt="logo" />
        <div class="app-brand__txt"><b>逑贝医疗</b><span>运营管理后台</span></div>
      </div>
      <div class="app-brand__sep"></div>
      <el-menu :default-active="route.path" router>
        <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon>
          <span>{{ m.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="app-header">
        <span class="header__title">{{ route.name }}</span>
        <div class="header__right">
          <el-tooltip :content="isDark ? '切换亮色' : '切换暗色'" placement="bottom">
            <el-button circle text @click="toggleTheme">
              <el-icon :size="18"><component :is="isDark ? Sunny : Moon" /></el-icon>
            </el-button>
          </el-tooltip>
          <el-tag size="small" effect="plain" type="primary">{{ ROLE_TEXT[role] || role }}</el-tag>
          <el-button text type="primary" @click="logout">退出登录</el-button>
        </div>
      </el-header>
      <el-main><router-view /></el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.app { height: 100vh; }
.header__title { font-size: 16px; font-weight: 600; }
.header__right { display: flex; align-items: center; gap: 10px; }
</style>
