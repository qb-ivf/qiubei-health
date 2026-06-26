<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import request from '@/api/request'

const router = useRouter()

// 运营数据大盘
const data = ref({})
const loading = ref(false)

const STATUS_TAG = {
  待支付: 'info', 候诊中: 'warning', 问诊中: '', 待审方: 'warning', 审方驳回: 'danger',
  已开方: 'success', 已完成: 'success', 已退款: 'danger', 已取消: 'info'
}

// 订单状态对应饼图配色
const STATUS_COLOR = {
  待支付: '#909399', 候诊中: '#e6a23c', 问诊中: '#409eff', 待审方: '#e6a23c',
  审方驳回: '#f56c6c', 已开方: '#67c23a', 已完成: '#00b578', 已退款: '#f56c6c', 已取消: '#c0c4cc'
}
const FALLBACK = '#2e90d9'

// 饼图扇区：累加百分比生成 conic-gradient + 图例
const pie = computed(() => {
  const dist = (data.value.status_dist || []).filter(d => d.count > 0)
  const total = dist.reduce((s, d) => s + d.count, 0)
  let acc = 0
  const segments = dist.map(d => {
    const color = STATUS_COLOR[d.status_text] || FALLBACK
    const start = (acc / total) * 100
    acc += d.count
    const end = (acc / total) * 100
    return { ...d, color, start, end, pct: Math.round((d.count / total) * 100) }
  })
  const gradient = segments.length
    ? segments.map(s => `${s.color} ${s.start}% ${s.end}%`).join(', ')
    : '#ebeef5 0% 100%'
  return { segments, total, gradient }
})

// 系统动态消息：操作图标
const ACTION_ICON = {
  创建账号: '👤', 编辑账号: '✏️', 删除账号: '🗑️', 重置密码: '🔑',
}
function activityIcon(a) {
  if (ACTION_ICON[a.action]) return ACTION_ICON[a.action]
  if (a.action.includes('审')) return '✅'
  if (a.action.includes('退')) return '↩️'
  if (a.action.includes('排班') || a.action.includes('号源')) return '🗓️'
  return '📌'
}

async function load() {
  loading.value = true
  try {
    data.value = await request.get('/admin/overview')
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <!-- 预警：在册医生但无可约号源（患者约不上号）-->
    <el-alert v-if="data.doctors_no_slots" type="warning" :closable="false" show-icon class="warn">
      <template #title>
        ⚠️ {{ data.doctors_no_slots }} 位在册医生暂无可约号源，患者约不上号
      </template>
      <div class="warn__body">
        <el-tag v-for="d in (data.doctors_no_slots_list || [])" :key="d.id" type="warning" effect="plain" class="warn__tag">
          {{ d.name }}（{{ d.dept || '—' }}）
        </el-tag>
        <el-button size="small" type="primary" @click="router.push('/doctor-schedule')">去排班管理</el-button>
      </div>
    </el-alert>

    <!-- 核心指标 -->
    <el-row :gutter="16">
      <el-col :span="6"><el-card><div class="k">今日订单</div><div class="v" style="color:#2e90d9">{{ data.today_orders ?? '—' }}</div><div class="sub">累计 {{ data.total_orders ?? 0 }}</div></el-card></el-col>
      <el-col :span="6"><el-card><div class="k">今日成交额</div><div class="v" style="color:#00b578">¥{{ data.today_revenue ?? '—' }}</div><div class="sub">累计 ¥{{ data.revenue_total ?? 0 }}</div></el-card></el-col>
      <el-col :span="6"><el-card><div class="k">成交订单</div><div class="v" style="color:#e0922e">{{ data.paid_orders ?? '—' }}</div><div class="sub">注册患者 {{ data.patients ?? 0 }}</div></el-card></el-col>
      <el-col :span="6"><el-card><div class="k">医生待提现余额</div><div class="v" style="color:#fa5151">¥{{ data.doctor_balance ?? '—' }}</div><div class="sub">待审提现 {{ data.pending_withdrawals ?? 0 }}</div></el-card></el-col>
    </el-row>

    <!-- 待办 -->
    <el-row :gutter="16" class="mt">
      <el-col :span="6"><el-card><div class="k">待审核处方</div><div class="v" :style="{color: (data.pending_rx? '#fa5151':'#909399')}">{{ data.pending_rx ?? '—' }}</div></el-card></el-col>
      <el-col :span="6"><el-card><div class="k">待资质终审</div><div class="v" :style="{color: (data.doctors_pending? '#fa5151':'#909399')}">{{ data.doctors_pending ?? '—' }}</div></el-card></el-col>
      <el-col :span="6"><el-card><div class="k">在册医生</div><div class="v" style="color:#2e90d9">{{ data.doctors_approved ?? '—' }}</div><div class="sub">总申请 {{ data.doctors_total ?? 0 }}</div></el-card></el-col>
      <el-col :span="6"><el-card><div class="k">待审提现单</div><div class="v" :style="{color: (data.pending_withdrawals? '#fa5151':'#909399')}">{{ data.pending_withdrawals ?? '—' }}</div></el-card></el-col>
    </el-row>

    <el-row :gutter="16" class="mt">
      <!-- 订单状态分布（饼图） -->
      <el-col :span="12">
        <el-card>
          <template #header>订单状态分布</template>
          <div v-if="pie.total" class="pie">
            <div class="pie__chart" :style="{ background: `conic-gradient(${pie.gradient})` }">
              <div class="pie__hole">
                <div class="pie__total">{{ pie.total }}</div>
                <div class="pie__label">总订单</div>
              </div>
            </div>
            <div class="pie__legend">
              <div v-for="s in pie.segments" :key="s.status" class="legend__item">
                <span class="legend__dot" :style="{ background: s.color }"></span>
                <span class="legend__name">{{ s.status_text }}</span>
                <span class="legend__n">{{ s.count }}</span>
                <span class="legend__pct">{{ s.pct }}%</span>
              </div>
            </div>
          </div>
          <div v-else class="muted">暂无订单数据</div>
        </el-card>
      </el-col>

      <!-- 系统动态消息 -->
      <el-col :span="12">
        <el-card class="feed-card">
          <template #header>系统动态消息</template>
          <el-scrollbar max-height="300px">
            <div v-if="(data.recent_activity || []).length" class="feed">
              <div v-for="a in data.recent_activity" :key="a.id" class="feed__item">
                <span class="feed__icon">{{ activityIcon(a) }}</span>
                <div class="feed__body">
                  <div class="feed__text">
                    <b>{{ a.actor_name }}</b> {{ a.action }}
                    <span v-if="a.detail" class="feed__detail">· {{ a.detail }}</span>
                  </div>
                  <div class="feed__time">{{ a.created_at }}</div>
                </div>
              </div>
            </div>
            <div v-else class="muted">暂无系统动态</div>
          </el-scrollbar>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.k { color: var(--el-text-color-secondary); font-size: 13px; }
.v { font-size: 30px; font-weight: 700; margin-top: 6px; }
.sub { color: var(--el-text-color-placeholder); font-size: 12px; margin-top: 4px; }
.mt { margin-top: 16px; }
.muted { color: var(--el-text-color-secondary); padding: 12px 0; }

/* 饼图 */
.pie { display: flex; align-items: center; gap: 28px; flex-wrap: wrap; }
.pie__chart {
  width: 160px; height: 160px; border-radius: 50%; flex: none;
  display: flex; align-items: center; justify-content: center;
}
.pie__hole {
  width: 96px; height: 96px; border-radius: 50%;
  background: var(--el-bg-color); display: flex; flex-direction: column;
  align-items: center; justify-content: center;
}
.pie__total { font-size: 26px; font-weight: 700; color: var(--el-text-color-primary); line-height: 1; }
.pie__label { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px; }
.pie__legend { flex: 1; min-width: 180px; display: flex; flex-direction: column; gap: 8px; }
.legend__item { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.legend__dot { width: 10px; height: 10px; border-radius: 2px; flex: none; }
.legend__name { color: var(--el-text-color-regular); }
.legend__n { margin-left: auto; font-weight: 700; color: var(--el-text-color-primary); }
.legend__pct { width: 42px; text-align: right; color: var(--el-text-color-secondary); }

/* 系统动态消息 */
.feed { display: flex; flex-direction: column; }
.feed__item { display: flex; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--el-border-color-lighter); }
.feed__item:last-child { border-bottom: none; }
.feed__icon { font-size: 16px; line-height: 20px; flex: none; }
.feed__body { flex: 1; min-width: 0; }
.feed__text { font-size: 13px; color: var(--el-text-color-regular); }
.feed__detail { color: var(--el-text-color-secondary); }
.feed__time { font-size: 12px; color: var(--el-text-color-placeholder); margin-top: 2px; }
.warn { margin-bottom: 16px; }
.warn__body { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 6px; }
.warn__tag { margin: 0; }
</style>
