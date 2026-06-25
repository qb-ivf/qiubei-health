<script setup>
import { ref, onMounted } from 'vue'
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

    <!-- 订单状态分布 -->
    <el-card class="mt">
      <template #header>订单状态分布</template>
      <div class="dist">
        <div v-for="d in (data.status_dist || [])" :key="d.status" class="dist__item">
          <el-tag :type="STATUS_TAG[d.status_text]" size="large">{{ d.status_text }}</el-tag>
          <span class="dist__n">{{ d.count }}</span>
        </div>
        <div v-if="!(data.status_dist || []).length" class="muted">暂无订单数据</div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.k { color: var(--el-text-color-secondary); font-size: 13px; }
.v { font-size: 30px; font-weight: 700; margin-top: 6px; }
.sub { color: var(--el-text-color-placeholder); font-size: 12px; margin-top: 4px; }
.mt { margin-top: 16px; }
.dist { display: flex; flex-wrap: wrap; gap: 28px; align-items: center; }
.dist__item { display: flex; align-items: center; gap: 8px; }
.dist__n { font-size: 22px; font-weight: 700; color: var(--el-text-color-primary); }
.muted { color: var(--el-text-color-secondary); }
.warn { margin-bottom: 16px; }
.warn__body { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 6px; }
.warn__tag { margin: 0; }
</style>
