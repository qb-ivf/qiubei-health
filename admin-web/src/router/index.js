import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/login', component: () => import('@/views/Login.vue') },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: '监管上报面板', component: () => import('@/views/Dashboard.vue') },
      { path: 'orders', name: '订单管理', component: () => import('@/views/Orders.vue') },
      { path: 'pharmacist', name: '药师审方', component: () => import('@/views/PharmacistReview.vue') },
      { path: 'doctor-audit', name: '医生资质终审', component: () => import('@/views/DoctorAudit.vue') },
      { path: 'drugs', name: '药品字典', component: () => import('@/views/Drugs.vue') },
      { path: 'finance', name: '财务对账提现', component: () => import('@/views/Finance.vue') }
    ]
  }
]

const router = createRouter({ history: createWebHashHistory(), routes })

router.beforeEach((to) => {
  if (to.path !== '/login' && !localStorage.getItem('token')) return '/login'
  return true
})

export default router
