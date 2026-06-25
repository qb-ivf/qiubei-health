import { createRouter, createWebHashHistory } from 'vue-router'

// 角色登陆后默认落地页
const ROLE_HOME = { admin: '/overview', pharmacist: '/pharmacist', finance: '/finance' }

const routes = [
  { path: '/login', component: () => import('@/views/Login.vue') },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: () => ROLE_HOME[localStorage.getItem('role')] || '/overview',
    children: [
      { path: 'overview', name: '运营概览', meta: { roles: ['admin'] }, component: () => import('@/views/Overview.vue') },
      { path: 'orders', name: '订单管理', meta: { roles: ['admin', 'finance'] }, component: () => import('@/views/Orders.vue') },
      { path: 'pharmacist', name: '药师审方', meta: { roles: ['admin', 'pharmacist'] }, component: () => import('@/views/PharmacistReview.vue') },
      { path: 'doctor-audit', name: '医生资质终审', meta: { roles: ['admin'] }, component: () => import('@/views/DoctorAudit.vue') },
      { path: 'drugs', name: '药品字典', meta: { roles: ['admin', 'pharmacist'] }, component: () => import('@/views/Drugs.vue') },
      { path: 'finance', name: '财务对账提现', meta: { roles: ['admin', 'finance'] }, component: () => import('@/views/Finance.vue') },
      { path: 'dashboard', name: '监管上报面板', meta: { roles: ['admin'] }, component: () => import('@/views/Dashboard.vue') },
      { path: 'audit-logs', name: '操作审计', meta: { roles: ['admin'] }, component: () => import('@/views/AuditLogs.vue') },
      { path: 'staff', name: '账号管理', meta: { roles: ['admin'] }, component: () => import('@/views/Staff.vue') }
    ]
  }
]

const router = createRouter({ history: createWebHashHistory(), routes })

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (to.path !== '/login' && !token) return '/login'
  const role = localStorage.getItem('role')
  if (to.meta?.roles && role && !to.meta.roles.includes(role)) return ROLE_HOME[role] || '/login'
  return true
})

export default router
