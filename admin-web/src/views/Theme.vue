<script setup>
import { computed } from 'vue'
import { THEMES, themeKey, setTheme, currentColors } from '@/composables/theme'

const current = computed(() => THEMES.find((t) => t.key === themeKey.value) || THEMES[0])
const colors = computed(() => currentColors())

const SWATCHES = [
  { key: 'primary', label: '主色 · 强调按钮/重点' },
  { key: 'secondary', label: '辅色 · 次要信息' },
  { key: 'accent', label: '强调色 · 装饰' },
  { key: 'danger', label: '错误色 · 警告' },
  { key: 'card', label: '容器 · 卡片底' },
  { key: 'bg', label: '背景 · 页面底' },
]

const TABLE = [
  { name: '张女士', status: '治疗', type: 'success' },
  { name: '李女士', status: '初诊', type: 'primary' },
  { name: '王女士', status: '随访', type: 'warning' },
]
</script>

<template>
  <div class="theme">
    <div class="theme__head">
      <div>
        <h2>系统主题</h2>
        <p>为您的工作界面选择最舒适的视觉风格，设置会自动保存到本地</p>
      </div>
      <el-tag size="large" effect="plain" round>
        <el-icon><component :is="current.icon" /></el-icon>
        <span style="margin-left:6px">当前主题：{{ current.name }}</span>
      </el-tag>
    </div>

    <!-- 主题模式 -->
    <el-card class="mb">
      <template #header><el-icon><Brush /></el-icon> 主题模式</template>
      <div class="grid">
        <div
          v-for="t in THEMES" :key="t.key"
          class="tcard" :class="{ 'tcard--on': t.key === themeKey.value }"
          @click="setTheme(t.key)"
        >
          <el-icon v-if="t.key === themeKey.value" class="tcard__check"><CircleCheckFilled /></el-icon>

          <!-- 预览小窗 -->
          <div v-if="t.key === 'system'" class="mini mini--sys">
            <span class="mini__auto">自动切换</span>
          </div>
          <div v-else class="mini" :style="{ background: t.colors.bg }">
            <div class="mini__bar" :style="{ background: t.colors.header }">
              <i style="background:#f56c6c"></i><i style="background:#e6a23c"></i><i style="background:#67c23a"></i>
            </div>
            <div class="mini__body">
              <div class="mini__side" :style="{ background: t.colors.sidebar }">
                <u :style="{ background: t.colors.primary }"></u><u></u><u></u>
              </div>
              <div class="mini__main">
                <div class="mini__block" :style="{ background: t.colors.card }"></div>
                <div class="mini__block" :style="{ background: t.colors.card }"></div>
                <div class="mini__block mini__block--wide" :style="{ background: t.colors.card }"></div>
              </div>
            </div>
          </div>

          <div class="tcard__title">
            <el-icon :style="{ color: t.colors ? t.colors.primary : 'var(--brand-primary)' }"><component :is="t.icon" /></el-icon>
            <b>{{ t.name }}</b>
            <el-tag v-if="t.tag" size="small" effect="light" type="success">{{ t.tag }}</el-tag>
          </div>
          <div class="tcard__desc">{{ t.desc }}</div>
        </div>
      </div>
    </el-card>

    <!-- 配色预览 -->
    <el-card class="mb">
      <template #header><el-icon><Brush /></el-icon> 配色预览</template>
      <p class="hint">下方色块展示当前主题的语义色彩定义，切换主题时会实时变化</p>
      <div class="swatches">
        <div v-for="s in SWATCHES" :key="s.key" class="sw">
          <div class="sw__color" :style="{ background: colors[s.key] }"></div>
          <div class="sw__label">{{ s.label }}</div>
        </div>
      </div>
    </el-card>

    <!-- 实时示例 -->
    <el-card>
      <template #header><el-icon><View /></el-icon> 实时示例</template>
      <div class="demo">
        <div class="demo__col">
          <div class="demo__t">今日新增患者</div>
          <div class="demo__big">24</div>
          <div class="demo__up"><el-icon><Top /></el-icon> +12% 较昨日</div>
        </div>
        <div class="demo__col">
          <div class="demo__t">数据表格</div>
          <el-table :data="TABLE" size="small" style="width:100%">
            <el-table-column prop="name" label="姓名" />
            <el-table-column label="状态" align="right">
              <template #default="{ row }"><el-tag :type="row.type" size="small" effect="light">{{ row.status }}</el-tag></template>
            </el-table-column>
          </el-table>
        </div>
        <div class="demo__col">
          <div class="demo__t">按钮与表单</div>
          <el-input placeholder="输入搜索内容..." :prefix-icon="'Search'" style="margin-bottom:14px" />
          <div class="demo__btns">
            <el-button type="primary">主操作</el-button>
            <el-button>次操作</el-button>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.theme__head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 18px; }
.theme__head h2 { margin: 0 0 6px; font-size: 22px; }
.theme__head p { margin: 0; color: var(--el-text-color-secondary); font-size: 13px; }
.mb { margin-bottom: 18px; }
.el-card__header .el-icon { vertical-align: -2px; margin-right: 6px; color: var(--brand-primary); }
.hint { margin: 0 0 16px; color: var(--el-text-color-secondary); font-size: 13px; }

.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
@media (max-width: 1100px) { .grid { grid-template-columns: repeat(2, 1fr); } }

.tcard {
  position: relative; border: 2px solid var(--el-border-color-lighter); border-radius: 12px;
  padding: 14px; cursor: pointer; transition: border-color .15s, transform .15s, box-shadow .15s;
}
.tcard:hover { transform: translateY(-2px); box-shadow: 0 6px 18px rgba(0, 0, 0, .08); }
.tcard--on { border-color: var(--brand-primary); }
.tcard__check { position: absolute; top: 10px; right: 10px; font-size: 22px; color: var(--brand-primary); background: var(--el-bg-color); border-radius: 50%; }
.tcard__title { display: flex; align-items: center; gap: 8px; margin-top: 12px; }
.tcard__title b { font-size: 15px; }
.tcard__desc { margin-top: 6px; font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.6; }

/* 预览小窗 */
.mini { height: 120px; border-radius: 9px; overflow: hidden; border: 1px solid var(--el-border-color-lighter); }
.mini__bar { height: 20px; display: flex; align-items: center; gap: 5px; padding: 0 8px; }
.mini__bar i { width: 7px; height: 7px; border-radius: 50%; }
.mini__body { display: flex; height: calc(100% - 20px); padding: 8px; gap: 8px; }
.mini__side { width: 30%; border-radius: 5px; padding: 7px 5px; display: flex; flex-direction: column; gap: 6px; }
.mini__side u { display: block; height: 7px; border-radius: 3px; background: rgba(128, 128, 128, .35); }
.mini__main { flex: 1; display: flex; flex-direction: column; gap: 7px; }
.mini__block { height: 22px; border-radius: 5px; box-shadow: 0 1px 3px rgba(0, 0, 0, .06); }
.mini__block--wide { flex: 1; }
.mini--sys { background: linear-gradient(135deg, #fafafa 0 50%, #1a1b22 50% 100%); position: relative; }
.mini--sys .mini__auto {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  background: var(--el-bg-color); color: var(--el-text-color-primary);
  font-size: 12px; padding: 4px 12px; border-radius: 20px; box-shadow: 0 2px 8px rgba(0, 0, 0, .15);
}

/* 配色预览 */
.swatches { display: grid; grid-template-columns: repeat(6, 1fr); gap: 16px; }
@media (max-width: 1100px) { .swatches { grid-template-columns: repeat(3, 1fr); } }
.sw__color { height: 110px; border-radius: 12px; border: 1px solid var(--el-border-color-lighter); }
.sw__label { margin-top: 10px; font-size: 12px; color: var(--el-text-color-secondary); text-align: center; }

/* 实时示例 */
.demo { display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; }
@media (max-width: 1100px) { .demo { grid-template-columns: 1fr; } }
.demo__t { font-size: 13px; color: var(--el-text-color-secondary); margin-bottom: 12px; }
.demo__big { font-size: 38px; font-weight: 800; color: var(--brand-primary); line-height: 1; }
.demo__up { margin-top: 10px; font-size: 12px; color: var(--el-color-success); display: flex; align-items: center; gap: 2px; }
.demo__btns { display: flex; gap: 12px; }
</style>
