// ESLint 平面配置（ESLint 10 + eslint-plugin-vue 10）
// 策略：只开能抓真问题的规则（vue/essential + no-unused-vars），不做风格类约束——
// 格式一致性交给 Prettier（npm run format），避免一次性全库重排的噪音。
import globals from 'globals'
import pluginVue from 'eslint-plugin-vue'
import eslintConfigPrettier from 'eslint-config-prettier'

export default [
  {
    ignores: ['dist/**', 'node_modules/**', '.build-*/**', '.build-check*/**', '.verify-build/**', '.vb*/**'],
  },
  ...pluginVue.configs['flat/essential'],
  {
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: { ...globals.browser },
    },
    rules: {
      // 未使用变量告警不阻断构建；吞错误的 catch（注释说明由全局 toast 兜底）属既有约定
      'no-unused-vars': ['warn', { args: 'none', caughtErrors: 'none' }],
      'vue/no-unused-vars': 'warn',
      // LoginView / NotFoundView 等单词组件名属既有命名
      'vue/multi-word-component-names': 'off',
    },
  },
  {
    // [架构豁免] 签到配置的 sections/* 采用「父传响应式配置草稿、子组件原位改字段」的
    // 表单编辑模式（草稿源自 store 的 taskConfigDraft / activeSet.config，保存时整体提交），
    // 属有意的 prop 对象嵌套变更而非误用；改为 emit 事件需重写 6 个组件 30+ 处，暂不翻新。
    files: ['src/components/signconfig/sections/**'],
    rules: {
      'vue/no-mutating-props': 'off',
    },
  },
  eslintConfigPrettier,
]
