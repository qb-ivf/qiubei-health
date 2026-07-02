<script setup>
import { ref, onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import request from '@/api/request'

// 医疗争议（不良事件）登记：天津监管 2.4.2 每日签到的数据源（合规记录只增改不删）
const list = ref([])
const loading = ref(false)
const dialog = ref(false)
const editing = ref(null)
const BUSINESS_TYPES = [
  { value: '1', label: '图文咨询' },
  { value: '4', label: '在线复诊' },
  { value: '5', label: '在线处方' },
  { value: '99', label: '其他' },
]
const EMPTY = {
  business_type: '4', patient_name: '', mobile: '', event_date: '',
  event_description: '', event_reason: '', take_steps: '', damage_degree: '',
  improvements: '', report_dept: '', report_person: '', order_id: null,
}
const form = reactive({ ...EMPTY })

async function load() {
  loading.value = true
  try { list.value = await request.get('/admin/disputes') || [] }
  finally { loading.value = false }
}
onMounted(load)

function typeLabel(v) { return BUSINESS_TYPES.find((t) => t.value === v)?.label || v }

function openAdd() {
  editing.value = null
  Object.assign(form, { ...EMPTY })
  dialog.value = true
}
function openEdit(row) {
  editing.value = row.id
  Object.assign(form, { ...row })
  dialog.value = true
}

async function save() {
  const required = ['patient_name', 'mobile', 'event_date', 'event_description', 'event_reason',
    'take_steps', 'damage_degree', 'improvements', 'report_dept', 'report_person']
  if (required.some((f) => !String(form[f] || '').trim())) {
    ElMessage.warning('监管上报要求所有字段必填，请补全')
    return
  }
  const payload = { ...form, order_id: form.order_id || null }
  if (editing.value) {
    await request.put(`/admin/disputes/${editing.value}`, payload)
    ElMessage.success('已更新')
  } else {
    await request.post('/admin/disputes', payload)
    ElMessage.success('已登记，将随每日批次上报监管平台')
  }
  dialog.value = false
  load()
}
</script>

<template>
  <el-card>
    <template #header>
      <div class="hd">
        <span>医疗争议（不良事件）登记 —— 每日随批次上报监管平台；当日无事件系统自动空签到</span>
        <el-button type="primary" @click="openAdd">登记事件</el-button>
      </div>
    </template>
    <el-table :data="list" v-loading="loading">
      <el-table-column prop="id" label="#" width="60" />
      <el-table-column label="业务类型" width="100">
        <template #default="{ row }"><el-tag>{{ typeLabel(row.business_type) }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="patient_name" label="患者" width="100" />
      <el-table-column prop="event_date" label="发生时间" width="150" />
      <el-table-column prop="event_description" label="事件描述" show-overflow-tooltip />
      <el-table-column prop="damage_degree" label="损害程度" width="140" show-overflow-tooltip />
      <el-table-column prop="report_dept" label="上报科室" width="110" />
      <el-table-column prop="report_person" label="上报人" width="90" />
      <el-table-column prop="report_date" label="登记时间" width="150" />
      <el-table-column label="操作" width="90">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="openEdit(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-dialog v-model="dialog" :title="editing ? '编辑不良事件' : '登记不良事件'" width="640px">
    <el-form :model="form" label-width="110px">
      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="业务类型" required>
            <el-select v-model="form.business_type">
              <el-option v-for="t in BUSINESS_TYPES" :key="t.value" :label="t.label" :value="t.value" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="发生时间" required>
            <el-date-picker v-model="form.event_date" type="datetime" format="YYYY-MM-DD HH:mm"
              value-format="YYYY-MM-DD HH:mm" placeholder="事件发生时间" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="患者姓名" required><el-input v-model="form.patient_name" /></el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="患者电话" required><el-input v-model="form.mobile" maxlength="15" /></el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="事件描述" required>
        <el-input v-model="form.event_description" type="textarea" :rows="3" maxlength="1024" show-word-limit />
      </el-form-item>
      <el-form-item label="主要原因" required>
        <el-input v-model="form.event_reason" type="textarea" :rows="2" maxlength="1024" />
      </el-form-item>
      <el-form-item label="采取的措施" required>
        <el-input v-model="form.take_steps" type="textarea" :rows="2" maxlength="1024" />
      </el-form-item>
      <el-form-item label="损害程度" required>
        <el-input v-model="form.damage_degree" type="textarea" :rows="2" maxlength="1024" placeholder="患者的损害程度描述" />
      </el-form-item>
      <el-form-item label="后续改进" required>
        <el-input v-model="form.improvements" type="textarea" :rows="2" maxlength="1024" />
      </el-form-item>
      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="上报科室" required><el-input v-model="form.report_dept" maxlength="30" /></el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="上报人" required><el-input v-model="form.report_person" maxlength="50" /></el-form-item>
        </el-col>
      </el-row>
    </el-form>
    <template #footer>
      <el-button @click="dialog = false">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.hd { display: flex; align-items: center; justify-content: space-between; }
</style>
