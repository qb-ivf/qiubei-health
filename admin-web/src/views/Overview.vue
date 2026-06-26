<script setup>
import { ref, computed, reactive, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import request from '@/api/request'
import { themeKey } from '@/composables/theme'

const router = useRouter()

// 读取当前生效主题的 CSS 变量，供 echarts 配色跟随系统主题
function themeVars() {
  const cs = getComputedStyle(document.documentElement)
  const v = (n, fb) => (cs.getPropertyValue(n).trim() || fb)
  return {
    text: v('--el-text-color-primary', '#e7e9f5'),
    sub: v('--el-text-color-secondary', '#8b93b8'),
    line: v('--el-border-color-lighter', 'rgba(255,255,255,.07)'),
    axis: v('--el-border-color', 'rgba(255,255,255,.14)'),
    fill: v('--el-fill-color-light', '#141a3a'),
    card: v('--el-bg-color', '#161c40'),
    primary: v('--brand-primary', '#7c83ff'),
    primaryLight: v('--el-color-primary-light-3', '#8b7cff'),
    rampLow: v('--el-color-primary-light-8', '#1b234d'),
  }
}

// 运营数据看板
const data = ref({})
const loading = ref(false)
const updatedAt = ref('')

// 订单/就诊阶段配色（环形图与状态标签共用）
const STATUS_COLOR = {
  待支付: '#8a8d99', 候诊中: '#f0a868', 问诊中: '#4aa3e0', 待审方: '#e6a23c',
  审方驳回: '#f07a7a', 已开方: '#67c23a', 已完成: '#2fd6a6', 已退款: '#f07a7a', 已取消: '#c0c4cc',
}

// —— 衍生数据 ——
const kpis = computed(() => {
  const d = data.value
  const delta = (d.today_new_patients ?? 0) - (d.yest_new_patients ?? 0)
  const deltaText = `较昨日 ${delta >= 0 ? '+' : ''}${delta}`
  return [
    { key: 'newp', label: '今日新增就诊人', value: d.today_new_patients ?? '—', sub: deltaText, icon: '👤', color: '#4aa3e0' },
    { key: 'total', label: '累计建档就诊人', value: d.patients ?? '—', sub: '实名就诊人总量', icon: '🗂️', color: '#2fd6a6' },
    { key: 'treat', label: '正在问诊', value: d.in_treatment ?? '—', sub: `今日订单 ${d.today_orders ?? 0}`, icon: '🩺', color: '#9b8cff' },
    { key: 'rev', label: '今日成交额', value: `¥${d.today_revenue ?? '—'}`, sub: `累计 ¥${d.revenue_total ?? 0}`, icon: '💰', color: '#f0a868' },
  ]
})

const todos = computed(() => {
  const d = data.value
  return [
    { label: '待审核处方', value: d.pending_rx ?? 0, path: '/pharmacist' },
    { label: '待资质终审', value: d.doctors_pending ?? 0, path: '/doctor-audit' },
    { label: '待审提现单', value: d.pending_withdrawals ?? 0, path: '/finance' },
    { label: '在册医生', value: d.doctors_approved ?? 0, path: '/doctor-audit' },
  ]
})

const ageDist = computed(() => {
  const rows = data.value.age_dist || []
  const total = rows.reduce((s, r) => s + r.count, 0) || 1
  return rows.map(r => ({ ...r, pct: Math.round((r.count / total) * 100) }))
})

const activityCount = computed(() => (data.value.recent_activity || []).length)
function activityIcon(a) {
  if (a.action?.includes('审')) return '✅'
  if (a.action?.includes('退')) return '↩️'
  if (a.action?.includes('排班') || a.action?.includes('号源')) return '🗓️'
  if (a.action?.includes('账号') || a.action?.includes('密码')) return '👤'
  return '📌'
}

// —— echarts ——
const mapEl = ref(null)
const pieEl = ref(null)
const trendEl = ref(null)
const charts = reactive({ map: null, pie: null, trend: null })
let mapReady = false

async function ensureMap() {
  if (mapReady) return
  try {
    const geo = await fetch('/geo/china.json').then(r => r.json())
    echarts.registerMap('china', geo)
    mapReady = true
  } catch (e) {
    mapReady = false
  }
}

function renderMap() {
  if (!charts.map || !mapReady) return
  const t = themeVars()
  const geo = data.value.patient_geo || []
  const max = Math.max(1, ...geo.map(g => g.count))
  charts.map.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', formatter: p => `${p.name}<br/>就诊人 ${p.value || 0}` },
    visualMap: {
      min: 0, max, left: 16, bottom: 16, calculable: true,
      text: ['高', '低'], textStyle: { color: t.sub },
      inRange: { color: [t.rampLow, t.primary] },
    },
    series: [{
      type: 'map', map: 'china', roam: false,
      label: { show: false }, scaleLimit: { min: 1, max: 3 },
      itemStyle: { areaColor: t.fill, borderColor: t.axis, borderWidth: 0.6 },
      emphasis: { label: { show: true, color: t.text }, itemStyle: { areaColor: t.primary } },
      data: geo.map(g => ({ name: g.province, value: g.count })),
    }],
  }, true)
}

function renderPie() {
  if (!charts.pie) return
  const t = themeVars()
  const dist = (data.value.status_dist || []).filter(d => d.count > 0)
  charts.pie.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, left: 'center', icon: 'circle', itemWidth: 9, itemHeight: 9, textStyle: { color: t.sub, fontSize: 11 } },
    series: [{
      type: 'pie', radius: ['46%', '70%'], center: ['50%', '44%'], avoidLabelOverlap: true,
      itemStyle: { borderColor: t.card, borderWidth: 2 },
      label: { color: t.sub, fontSize: 11, formatter: '{b}\n{d}%' },
      labelLine: { length: 8, length2: 8 },
      data: dist.map(d => ({ name: d.status_text, value: d.count, itemStyle: { color: STATUS_COLOR[d.status_text] || t.primary } })),
    }],
  }, true)
}

function renderTrend() {
  if (!charts.trend) return
  const t = themeVars()
  const rows = data.value.growth_trend || []
  charts.trend.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 40, right: 16, top: 18, bottom: 26 },
    xAxis: {
      type: 'category', data: rows.map(r => r.month.slice(5) + '月'),
      axisLabel: { color: t.sub, fontSize: 10 },
      axisLine: { lineStyle: { color: t.axis } }, axisTick: { show: false },
    },
    yAxis: {
      type: 'value', minInterval: 1,
      splitLine: { lineStyle: { color: t.line } },
      axisLabel: { color: t.sub, fontSize: 10 },
    },
    series: [{
      type: 'bar', data: rows.map(r => r.count), barWidth: '46%',
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: t.primaryLight }, { offset: 1, color: t.primary },
        ]),
      },
    }],
  }, true)
}

function renderAll() { renderMap(); renderPie(); renderTrend() }

function onResize() { charts.map?.resize(); charts.pie?.resize(); charts.trend?.resize() }

async function initCharts() {
  await ensureMap()
  await nextTick()
  if (mapEl.value && !charts.map) charts.map = echarts.init(mapEl.value)
  if (pieEl.value && !charts.pie) charts.pie = echarts.init(pieEl.value)
  if (trendEl.value && !charts.trend) charts.trend = echarts.init(trendEl.value)
  renderAll()
}

async function load() {
  loading.value = true
  try {
    data.value = await request.get('/admin/overview')
    const now = new Date()
    updatedAt.value = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
    await nextTick()
    renderAll()
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await load()
  await initCharts()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  charts.map?.dispose(); charts.pie?.dispose(); charts.trend?.dispose()
})
watch(data, () => renderAll())
// 主题切换：CSS 变量更新后重新着色图表
watch(themeKey, () => nextTick(renderAll))
</script>

<template>
  <div class="board" v-loading="loading">
    <!-- 预警：在册医生但无可约号源 -->
    <el-alert v-if="data.doctors_no_slots" type="warning" :closable="false" show-icon class="board__warn">
      <template #title>⚠️ {{ data.doctors_no_slots }} 位在册医生暂无可约号源，患者约不上号</template>
      <div class="warn__body">
        <el-tag v-for="d in (data.doctors_no_slots_list || [])" :key="d.id" type="warning" effect="plain" class="warn__tag">
          {{ d.name }}（{{ d.dept || '—' }}）
        </el-tag>
        <el-button size="small" type="primary" @click="router.push('/doctor-schedule')">去排班管理</el-button>
      </div>
    </el-alert>

    <!-- 标题栏 -->
    <div class="board__head">
      <div>
        <h2 class="board__title">运营数据看板</h2>
        <p class="board__sub">实时运营数据分析与就诊人分布监控</p>
      </div>
      <div class="board__actions">
        <span v-if="updatedAt" class="board__time">更新于 {{ updatedAt }}</span>
        <el-button type="primary" :icon="'Refresh'" @click="load">实时更新</el-button>
      </div>
    </div>

    <div class="board__main">
      <!-- 左侧主区 -->
      <div class="board__col">
        <!-- KPI -->
        <div class="kpis">
          <div v-for="k in kpis" :key="k.key" class="kpi">
            <div class="kpi__info">
              <div class="kpi__label">{{ k.label }}</div>
              <div class="kpi__value">{{ k.value }}</div>
              <div class="kpi__sub">{{ k.sub }}</div>
            </div>
            <div class="kpi__icon" :style="{ background: k.color + '22', color: k.color }">{{ k.icon }}</div>
          </div>
        </div>

        <!-- 待办 -->
        <div class="todos">
          <div v-for="t in todos" :key="t.label" class="todo" @click="router.push(t.path)">
            <span class="todo__n" :class="{ 'todo__n--hot': t.value > 0 }">{{ t.value }}</span>
            <span class="todo__label">{{ t.label }}</span>
          </div>
        </div>

        <!-- 地图 + 阶段占比 -->
        <div class="grid grid--2">
          <div class="panel panel--map">
            <div class="panel__head">全国就诊人分布图<span class="panel__tag">实名就诊人省份</span></div>
            <div ref="mapEl" class="chart chart--map"></div>
          </div>
          <div class="panel">
            <div class="panel__head">就诊阶段占比</div>
            <div ref="pieEl" class="chart chart--pie"></div>
          </div>
        </div>

        <!-- 增长趋势 + 年龄分布 -->
        <div class="grid grid--2">
          <div class="panel">
            <div class="panel__head">就诊人增长趋势<span class="panel__tag">近 12 个月</span></div>
            <div ref="trendEl" class="chart chart--trend"></div>
          </div>
          <div class="panel">
            <div class="panel__head">就诊人年龄分布</div>
            <div class="ages">
              <div v-for="a in ageDist" :key="a.label" class="age">
                <span class="age__label">{{ a.label }}</span>
                <div class="age__track"><div class="age__bar" :style="{ width: a.pct + '%' }"></div></div>
                <span class="age__pct">{{ a.pct }}%</span>
              </div>
              <div v-if="!ageDist.length" class="board__empty">暂无年龄数据</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：系统动态消息 -->
      <aside class="panel feed">
        <div class="panel__head">
          系统动态消息
          <span v-if="activityCount" class="feed__badge">新消息 {{ activityCount }}</span>
        </div>
        <el-scrollbar class="feed__scroll">
          <div v-if="activityCount" class="feed__list">
            <div v-for="a in data.recent_activity" :key="a.id" class="feed__item">
              <span class="feed__icon">{{ activityIcon(a) }}</span>
              <div class="feed__body">
                <div class="feed__text"><b>{{ a.actor_name }}</b> {{ a.action }}</div>
                <div v-if="a.detail" class="feed__detail">{{ a.detail }}</div>
                <div class="feed__time">{{ a.created_at }}</div>
              </div>
            </div>
          </div>
          <div v-else class="board__empty">暂无系统动态</div>
        </el-scrollbar>
      </aside>
    </div>
  </div>
</template>

<style scoped>
/* 看板配色跟随全局主题（浅色/深色/晨曦/松韵/墨夜均自动适配） */
.board {
  --bd-card: var(--el-bg-color);
  --bd-line: var(--el-border-color-lighter);
  --bd-text: var(--el-text-color-primary);
  --bd-sub: var(--el-text-color-secondary);
  --bd-primary: var(--brand-primary);
  color: var(--bd-text);
}

.board__warn { margin-bottom: 14px; }
.warn__body { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 6px; }
.warn__tag { margin: 0; }

.board__head { display: flex; align-items: flex-end; justify-content: space-between; margin-bottom: 16px; }
.board__title { margin: 0; font-size: 22px; font-weight: 800; letter-spacing: 1px; }
.board__sub { margin: 4px 0 0; font-size: 13px; color: var(--bd-sub); }
.board__actions { display: flex; align-items: center; gap: 12px; }
.board__time { font-size: 12px; color: var(--bd-sub); }

.board__main { display: flex; gap: 16px; align-items: stretch; }
.board__col { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 16px; }

/* KPI */
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.kpi {
  background: var(--bd-card); border: 1px solid var(--bd-line); border-radius: 14px;
  padding: 18px; display: flex; align-items: center; justify-content: space-between;
}
.kpi__label { font-size: 13px; color: var(--bd-sub); }
.kpi__value { font-size: 28px; font-weight: 800; margin: 6px 0 4px; }
.kpi__sub { font-size: 12px; color: var(--bd-sub); }
.kpi__icon {
  width: 46px; height: 46px; border-radius: 12px; flex: none;
  display: flex; align-items: center; justify-content: center; font-size: 22px;
}

/* 待办 */
.todos { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.todo {
  background: var(--bd-card); border: 1px solid var(--bd-line); border-radius: 12px;
  padding: 12px 16px; display: flex; align-items: center; gap: 10px; cursor: pointer;
  transition: border-color .15s, transform .15s;
}
.todo:hover { border-color: var(--bd-primary); transform: translateY(-1px); }
.todo__n { font-size: 22px; font-weight: 800; color: var(--bd-sub); }
.todo__n--hot { color: #f07a7a; }
.todo__label { font-size: 13px; color: var(--bd-sub); }

/* 面板通用 */
.panel { background: var(--bd-card); border: 1px solid var(--bd-line); border-radius: 14px; padding: 16px; }
.panel__head { font-size: 15px; font-weight: 700; display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.panel__tag {
  font-size: 11px; font-weight: 500; color: var(--bd-primary);
  background: var(--el-color-primary-light-9); border-radius: 6px; padding: 2px 8px;
}
.grid { display: grid; gap: 16px; }
.grid--2 { grid-template-columns: 1.4fr 1fr; }

.chart { width: 100%; }
.chart--map { height: 380px; }
.chart--pie { height: 300px; }
.chart--trend { height: 240px; }

/* 年龄分布（CSS 进度条） */
.ages { display: flex; flex-direction: column; gap: 16px; padding: 8px 2px; }
.age { display: flex; align-items: center; gap: 12px; }
.age__label { width: 64px; font-size: 12px; color: var(--bd-sub); flex: none; }
.age__track { flex: 1; height: 8px; border-radius: 6px; background: var(--el-fill-color); overflow: hidden; }
.age__bar { height: 100%; border-radius: 6px; background: linear-gradient(90deg, var(--el-color-primary-light-3), var(--brand-primary)); }
.age__pct { width: 40px; text-align: right; font-size: 12px; font-weight: 700; flex: none; }

/* 系统动态消息 */
.feed { width: 360px; flex: none; display: flex; flex-direction: column; }
.feed__badge {
  margin-left: auto; font-size: 11px; font-weight: 600; color: #fff;
  background: var(--bd-primary); border-radius: 6px; padding: 2px 8px;
}
.feed__scroll { flex: 1; }
.feed__list { display: flex; flex-direction: column; }
.feed__item { display: flex; gap: 10px; padding: 12px 4px; border-bottom: 1px solid var(--bd-line); }
.feed__item:last-child { border-bottom: none; }
.feed__icon {
  width: 30px; height: 30px; flex: none; border-radius: 8px; font-size: 15px;
  display: flex; align-items: center; justify-content: center;
  background: var(--el-color-primary-light-9);
}
.feed__body { flex: 1; min-width: 0; }
.feed__text { font-size: 13px; color: var(--bd-text); }
.feed__text b { color: var(--bd-text); }
.feed__detail { font-size: 12px; color: var(--bd-sub); margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.feed__time { font-size: 11px; color: var(--el-text-color-placeholder); margin-top: 3px; }

.board__empty { color: var(--bd-sub); padding: 20px 0; text-align: center; font-size: 13px; }

/* 卡片内 Element 滚动条/标签深色适配 */
:deep(.el-scrollbar__bar) { opacity: .3; }

@media (max-width: 1280px) {
  .board__main { flex-direction: column; }
  .feed { width: auto; }
  .grid--2 { grid-template-columns: 1fr; }
  .kpis, .todos { grid-template-columns: repeat(2, 1fr); }
}
</style>
