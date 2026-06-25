import { ref } from 'vue'

// 亮/暗主题切换，持久化到 localStorage
const KEY = 'theme'
export const isDark = ref(localStorage.getItem(KEY) === 'dark')

function apply() {
  document.documentElement.classList.toggle('dark', isDark.value)
}

export function initTheme() {
  apply()
}

export function toggleTheme() {
  isDark.value = !isDark.value
  localStorage.setItem(KEY, isDark.value ? 'dark' : 'light')
  apply()
}
