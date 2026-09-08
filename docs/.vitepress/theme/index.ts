import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import LifecycleArchitecture from './components/LifecycleArchitecture.vue'
import './custom.css'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('LifecycleArchitecture', LifecycleArchitecture)
  },
} satisfies Theme
