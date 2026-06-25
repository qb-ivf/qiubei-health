import { ref } from 'vue'

// ===== 多主题引擎（参考集团 SaaS「辅助生殖大数据平台」）=====
// 选择持久化到 localStorage；'system' 跟随操作系统深浅色。
const KEY = 'theme'

// 每个主题：key / 名称 / 描述 / 标签 / 图标 / 模式(light|dark|system) / 预览六色
export const THEMES = [
  {
    key: 'light', name: '浅色模式', tag: '', icon: 'Sunny', mode: 'light',
    desc: '明亮通透的经典界面，白天使用最舒适，适合长时间办公',
    colors: { primary: '#2e90d9', secondary: '#5ac8b8', accent: '#f0a050', danger: '#e85d5d', card: '#ffffff', bg: '#f2f5f9', sidebar: '#ffffff', header: '#ffffff' },
  },
  {
    key: 'dark', name: '深色模式', tag: '', icon: 'Moon', mode: 'dark',
    desc: '沉浸式暗色界面，降低光线刺激，夜晚使用更护眼',
    colors: { primary: '#4aa3e0', secondary: '#5fcabb', accent: '#f0a868', danger: '#f07a7a', card: '#1d1e26', bg: '#141418', sidebar: '#1a1b22', header: '#1a1b22' },
  },
  {
    key: 'system', name: '跟随系统', tag: '', icon: 'Monitor', mode: 'system',
    desc: '根据操作系统设置自动切换浅色或深色', colors: null,
  },
  {
    key: 'chenxi', name: '晨曦', tag: '温暖治愈', icon: 'Sunrise', mode: 'light',
    desc: '奶白米色搭琥珀暖橙，如清晨阳光般柔和，缓解候诊焦虑',
    colors: { primary: '#d98a3d', secondary: '#e0b07a', accent: '#c2724a', danger: '#c0504d', card: '#fffaf3', bg: '#faf2e6', sidebar: '#fff6ec', header: '#fdf4e7' },
  },
  {
    key: 'songyun', name: '松韵', tag: '自然希望', icon: 'Apple', mode: 'light',
    desc: '松针绿点缀木色，象征新生与希望，传递生命的温度',
    colors: { primary: '#2f8f5b', secondary: '#6ba588', accent: '#b5895a', danger: '#c2403a', card: '#ffffff', bg: '#eaf2ea', sidebar: '#f3f8f4', header: '#f1f7f1' },
  },
  {
    key: 'moye', name: '墨夜', tag: '沉浸护眼', icon: 'MoonNight', mode: 'dark',
    desc: '深邃紫蓝衬淡紫光，优雅典雅，夜班长时间工作最护眼',
    colors: { primary: '#ab93f5', secondary: '#5fdcc0', accent: '#f0a868', danger: '#f48ba6', card: '#262a40', bg: '#1f2136', sidebar: '#191b2c', header: '#1a1c2e' },
  },
]

export const themeKey = ref(localStorage.getItem(KEY) || 'songyun')

function meta(key) { return THEMES.find((t) => t.key === key) || THEMES[0] }

function prefersDark() {
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
}

// 'system' 解析为实际生效的 light/dark；其余原样
function effectiveKey(key) {
  const t = meta(key)
  if (t.mode === 'system') return prefersDark() ? 'dark' : 'light'
  return key
}

function apply() {
  const eff = effectiveKey(themeKey.value)
  const isDark = meta(eff).mode === 'dark'
  document.documentElement.setAttribute('data-theme', eff)
  document.documentElement.classList.toggle('dark', isDark)
}

let mql
export function initTheme() {
  apply()
  mql = window.matchMedia('(prefers-color-scheme: dark)')
  const onChange = () => { if (themeKey.value === 'system') apply() }
  mql.addEventListener ? mql.addEventListener('change', onChange) : mql.addListener(onChange)
}

export function setTheme(key) {
  themeKey.value = key
  localStorage.setItem(KEY, key)
  apply()
}

// 当前生效主题的六色（system 解析为 light/dark），供「配色预览」实时展示
export function currentColors() {
  return meta(effectiveKey(themeKey.value)).colors
}
