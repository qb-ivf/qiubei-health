import { ref } from 'vue'
import request from '@/api/request'

// 缺号源医生数（侧边栏「排班管理」红点角标共享状态）
export const noSlotCount = ref(0)

export async function refreshAlerts() {
  if (localStorage.getItem('role') !== 'admin') return
  try {
    const res = await request.get('/admin/no-slot-doctors')
    noSlotCount.value = res.count || 0
  } catch (e) { /* 拦截器已提示 */ }
}
