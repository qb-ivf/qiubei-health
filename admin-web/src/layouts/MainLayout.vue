<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from '@/api/request'
const route = useRoute()
const router = useRouter()

const ROLE_TEXT = { admin: '超级管理员', pharmacist: '审方药师', finance: '财务' }
const role = localStorage.getItem('role')
const uname = localStorage.getItem('uname') || (role || '用户')
const avatarChar = (uname[0] || 'U').toUpperCase()

const isCollapse = ref(false)

// 导航：顶级项 或 分组(children)。按角色过滤，空组自动隐藏。
const NAV = [
  { path: '/overview', title: '运营概览', icon: 'Odometer', roles: ['admin'] },
  {
    title: '运营管理', icon: 'Management', children: [
      { path: '/orders', title: '订单管理', icon: 'List', roles: ['admin', 'finance'] },
      { path: '/pharmacist', title: '药师审方', icon: 'DocumentChecked', roles: ['admin', 'pharmacist'] },
      { path: '/drugs', title: '药品字典', icon: 'FirstAidKit', roles: ['admin', 'pharmacist'] },
    ],
  },
  {
    title: '医生与审核', icon: 'Postcard', children: [
      { path: '/doctor-audit', title: '医生资质终审', icon: 'Postcard', roles: ['admin'] },
      { path: '/doctor-schedule', title: '排班管理', icon: 'Calendar', roles: ['admin'] },
    ],
  },
  {
    title: '财务管理', icon: 'Money', children: [
      { path: '/finance', title: '财务对账提现', icon: 'Money', roles: ['admin', 'finance'] },
    ],
  },
  {
    title: '监管合规', icon: 'DataLine', children: [
      { path: '/dashboard', title: '监管上报面板', icon: 'DataLine', roles: ['admin'] },
    ],
  },
  {
    title: '系统设置', icon: 'Setting', children: [
      { path: '/audit-logs', title: '操作审计', icon: 'Tickets', roles: ['admin'] },
      { path: '/staff', title: '账号管理', icon: 'UserFilled', roles: ['admin'] },
      { path: '/theme', title: '系统主题', icon: 'Brush', roles: ['admin', 'pharmacist', 'finance'] },
    ],
  },
]

const nav = computed(() => NAV.map((n) => {
  if (n.children) {
    const ch = n.children.filter((c) => c.roles.includes(role))
    return ch.length ? { ...n, children: ch } : null
  }
  return n.roles.includes(role) ? n : null
}).filter(Boolean))

function onCommand(cmd) {
  if (cmd === 'logout') {
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    router.replace('/login')
  }
}

// 缺号源医生数 → 排班管理菜单红点角标（仅 admin 可见该菜单/接口）
const noSlotCount = ref(0)
async function loadAlerts() {
  if (role !== 'admin') return
  try {
    const res = await request.get('/admin/no-slot-doctors')
    noSlotCount.value = res.count || 0
  } catch (e) { /* 拦截器已提示 */ }
}
function itemBadge(path) { return path === '/doctor-schedule' ? noSlotCount.value : 0 }
function groupHasAlert(n) {
  return !!(n.children && n.children.some((c) => itemBadge(c.path) > 0))
}
onMounted(loadAlerts)
</script>

<template>
  <el-container class="app">
    <el-header class="topbar">
      <div class="topbar__left">
        <el-icon class="topbar__toggle" @click="isCollapse = !isCollapse">
          <component :is="isCollapse ? 'Expand' : 'Fold'" />
        </el-icon>
        <img src="/logo.png" class="topbar__logo" alt="logo" />
        <div class="topbar__brand">
          <b>逑贝医疗</b>
          <span class="topbar__divider"></span>
          <span class="topbar__sub">运营管理后台</span>
        </div>
      </div>
      <div class="topbar__right">
        <el-tooltip content="消息通知" placement="bottom"><el-icon class="topbar__ico"><Bell /></el-icon></el-tooltip>
        <el-tooltip content="帮助" placement="bottom"><el-icon class="topbar__ico"><QuestionFilled /></el-icon></el-tooltip>
        <el-dropdown trigger="click" @command="onCommand">
          <div class="topbar__user">
            <span class="topbar__avatar">{{ avatarChar }}</span>
            <div class="topbar__uinfo"><b>{{ uname }}</b><span>{{ ROLE_TEXT[role] || role }}</span></div>
            <el-icon><ArrowDown /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="theme" @click="router.push('/theme')">
                <el-icon><Brush /></el-icon>系统主题
              </el-dropdown-item>
              <el-dropdown-item command="logout" divided>
                <el-icon><SwitchButton /></el-icon>退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-header>

    <el-container class="app__body">
      <el-aside :width="isCollapse ? '64px' : '224px'" class="app-aside">
        <div v-show="!isCollapse" class="app-aside__label">主菜单</div>
        <el-menu :default-active="route.path" :collapse="isCollapse" :collapse-transition="false" router unique-opened>
          <template v-for="n in nav" :key="n.path || n.title">
            <el-menu-item v-if="!n.children" :index="n.path">
              <el-icon><component :is="n.icon" /></el-icon>
              <template #title>{{ n.title }}</template>
            </el-menu-item>
            <el-sub-menu v-else :index="n.title">
              <template #title>
                <el-badge is-dot :hidden="!groupHasAlert(n)" class="nav-dot">
                  <el-icon><component :is="n.icon" /></el-icon>
                </el-badge>
                <span>{{ n.title }}</span>
              </template>
              <el-menu-item v-for="c in n.children" :key="c.path" :index="c.path">
                <el-icon><component :is="c.icon" /></el-icon>
                <template #title>
                  <span>{{ c.title }}</span>
                  <el-badge v-if="itemBadge(c.path)" :value="itemBadge(c.path)" :max="99" class="nav-badge" />
                </template>
              </el-menu-item>
            </el-sub-menu>
          </template>
        </el-menu>
        <div v-show="!isCollapse" class="app-aside__foot">
          <div class="app-aside__pill"><el-icon><FirstAidKit /></el-icon>逑贝互联网医院</div>
          <div class="app-aside__copy">© 2026 逑贝医疗</div>
        </div>
      </el-aside>
      <el-main><router-view /></el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.app { height: 100vh; }
.app__body { height: calc(100vh - 58px); }

/* 菜单角标：组图标右上红点（折叠时也可见）+ 排班管理项的数字角标 */
:deep(.nav-dot) { vertical-align: middle; margin-right: 5px; }
:deep(.nav-dot .el-icon) { margin-right: 0; }
:deep(.nav-badge) { margin-left: 8px; vertical-align: middle; }
:deep(.nav-badge .el-badge__content) { border: none; }
</style>
