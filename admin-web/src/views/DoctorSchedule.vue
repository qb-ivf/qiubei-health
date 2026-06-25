<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/api/request'
import { refreshAlerts } from '@/composables/alerts'

// 预设可排时段（与医生端小程序一致：上午 4 + 下午 4）
const PRESET = [
  { start: '09:00', end: '09:30' }, { start: '09:30', end: '10:00' },
  { start: '10:00', end: '10:30' }, { start: '10:30', end: '11:00' },
  { start: '14:00', end: '14:30' }, { start: '14:30', end: '15:00' },
  { start: '15:00', end: '15:30' }, { start: '15:30', end: '16:00' },
]
const WEEK = ['日', '一', '二', '三', '四', '五', '六']
const pad = (n) => (n < 10 ? '0' + n : '' + n)

const doctors = ref([])
const docId = ref(null)
const days = ref([])
const activeDay = ref('')
const quota = ref(5)
const slots = ref([])       // [{start,end,open,id?,remaining,quota}]
const loading = ref(false)

function buildDays() {
  const today = new Date()
  const arr = []
  for (let i = 0; i < 7; i++) {
    const d = new Date(today.getTime() + i * 86400000)
    const date = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
    const label = i === 0 ? '今天' : i === 1 ? '明天' : '周' + WEEK[d.getDay()]
    arr.push({ date, label, md: `${pad(d.getMonth() + 1)}-${pad(d.getDate())}` })
  }
  days.value = arr
  activeDay.value = arr[0].date
}

async function loadDoctors() {
  try {
    doctors.value = await request.get('/admin/doctors', { params: { status: 'approved' } })
    if (doctors.value.length && !docId.value) docId.value = doctors.value[0].id
    if (docId.value) await load()
  } catch (e) { /* 拦截器已提示 */ }
}

async function load() {
  if (!docId.value) { slots.value = []; return }
  loading.value = true
  try {
    const list = await request.get(`/admin/doctors/${docId.value}/schedule`, { params: { day: activeDay.value } })
    const map = {}
    ;(list || []).forEach((s) => { map[s.start_time] = s })
    slots.value = PRESET.map((p) => {
      const s = map[p.start]
      return s
        ? { start: p.start, end: p.end, open: true, id: s.id, remaining: s.remaining, quota: s.quota }
        : { start: p.start, end: p.end, open: false }
    })
  } finally { loading.value = false }
}

function onDoctorChange() { load() }
function selectDay(d) { activeDay.value = d; load() }

async function openSlot(s) {
  try {
    await request.post(`/admin/doctors/${docId.value}/slots`, {
      day: activeDay.value, quota: quota.value, times: [{ start: s.start, end: s.end }],
    })
    ElMessage.success('已开号')
    load(); refreshAlerts()
  } catch (e) { /* 拦截器已提示 */ }
}

async function openAll() {
  try {
    const out = await request.post(`/admin/doctors/${docId.value}/slots`, {
      day: activeDay.value, quota: quota.value, times: PRESET,
    })
    ElMessage.success(`已开放 ${out.length} 个新时段`)
    load(); refreshAlerts()
  } catch (e) { /* 拦截器已提示 */ }
}

async function changeQuota(s, delta) {
  const next = s.quota + delta
  if (next < 1) return
  try {
    await request.patch(`/admin/slots/${s.id}`, { quota: next })
    load(); refreshAlerts()
  } catch (e) { /* 拦截器已提示 */ }
}

async function delSlot(s) {
  if (s.remaining < s.quota) { ElMessage.warning('该时段已有预约，不可删除'); return }
  try {
    await ElMessageBox.confirm(`确认删除 ${activeDay.value} ${s.start} 这个时段？`, '删除号源', { type: 'warning' })
  } catch { return }
  try {
    await request.delete(`/admin/slots/${s.id}`)
    ElMessage.success('已删除')
    load(); refreshAlerts()
  } catch (e) { /* 拦截器已提示 */ }
}

onMounted(() => { buildDays(); loadDoctors() })
// 离开排班页时再刷新一次角标，确保补完号源后红点及时消掉
onBeforeUnmount(refreshAlerts)
</script>

<template>
  <div>
    <el-alert type="info" :closable="false" show-icon class="tip"
      title="代医生管理号源：开号 / 加减号 / 删号与医生端小程序共用同一套逻辑，号源扣减以 Redis 为准。医生本人也可在小程序自助排班。" />

    <el-card>
      <div class="bar">
        <div class="bar__left">
          <span class="lbl">医生</span>
          <el-select v-model="docId" filterable placeholder="选择已在册医生" style="width:240px" @change="onDoctorChange">
            <el-option v-for="d in doctors" :key="d.id" :label="`${d.name}（${d.dept || '—'}）`" :value="d.id" />
          </el-select>
        </div>
        <div class="bar__right">
          <span class="lbl">开号号数</span>
          <el-input-number v-model="quota" :min="1" :max="50" size="default" />
          <el-button type="primary" :disabled="!docId" @click="openAll">一键开放全天</el-button>
        </div>
      </div>

      <!-- 日期切换 -->
      <div class="days">
        <div v-for="d in days" :key="d.date" class="day" :class="{ 'day--on': d.date === activeDay }" @click="selectDay(d.date)">
          <div class="day__lbl">{{ d.label }}</div>
          <div class="day__md">{{ d.md }}</div>
        </div>
      </div>

      <!-- 时段网格 -->
      <div v-loading="loading" class="grid">
        <div v-for="s in slots" :key="s.start" class="slot" :class="{ 'slot--on': s.open }">
          <div class="slot__time">{{ s.start }}–{{ s.end }}</div>
          <template v-if="s.open">
            <div class="slot__num">
              <span class="slot__remain">剩 {{ s.remaining }}</span> / 共 {{ s.quota }} 号
            </div>
            <div class="slot__ops">
              <el-button-group>
                <el-button size="small" :icon="'Minus'" @click="changeQuota(s, -1)" />
                <el-button size="small" :icon="'Plus'" @click="changeQuota(s, 1)" />
              </el-button-group>
              <el-button size="small" text type="danger" :icon="'Delete'" @click="delSlot(s)" />
            </div>
          </template>
          <template v-else>
            <div class="slot__closed">未开放</div>
            <el-button size="small" type="primary" plain :disabled="!docId" @click="openSlot(s)">开号</el-button>
          </template>
        </div>
      </div>

      <el-empty v-if="!docId" description="请选择一位在册医生" :image-size="80" />
    </el-card>
  </div>
</template>

<style scoped>
.tip { margin-bottom: 14px; }
.bar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
.bar__left, .bar__right { display: flex; align-items: center; gap: 10px; }
.lbl, .lbl { color: var(--el-text-color-secondary); font-size: 13px; }
.days { display: flex; gap: 10px; margin: 18px 0; flex-wrap: wrap; }
.day {
  width: 78px; text-align: center; padding: 8px 0; border-radius: 10px; cursor: pointer;
  border: 1px solid var(--el-border-color-light); transition: all .15s;
}
.day:hover { border-color: var(--el-color-primary); }
.day--on { background: var(--el-color-primary); border-color: var(--el-color-primary); color: #fff; }
.day__lbl { font-size: 13px; font-weight: 600; }
.day__md { font-size: 12px; opacity: .8; margin-top: 2px; }
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; min-height: 80px; }
@media (max-width: 900px) { .grid { grid-template-columns: repeat(2, 1fr); } }
.slot {
  border: 1px solid var(--el-border-color-lighter); border-radius: 12px; padding: 14px;
  display: flex; flex-direction: column; gap: 10px; background: var(--el-fill-color-lighter);
}
.slot--on { background: var(--el-color-primary-light-9); border-color: var(--el-color-primary-light-7); }
.slot__time { font-weight: 700; font-size: 15px; }
.slot__num { font-size: 13px; color: var(--el-text-color-regular); }
.slot__remain { color: var(--el-color-success); font-weight: 600; }
.slot__closed { font-size: 13px; color: var(--el-text-color-placeholder); }
.slot__ops { display: flex; align-items: center; justify-content: space-between; }
</style>
