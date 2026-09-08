import { defineConfig } from 'vitepress'

export default defineConfig({
  lang: 'zh-CN',
  title: 'Project Lifecycle',
  description: '面向用户的项目全流程开发与跨会话接力教程',
  cleanUrls: true,
  head: [['link', { rel: 'icon', href: '/favicon.svg' }]],
  themeConfig: {
    nav: [
      { text: '教程首页', link: '/' },
      { text: '总索引', link: '/reference/' },
      { text: '全流程', link: '/guide/full-workflow' },
      { text: '恢复与接力', link: '/guide/resume' },
      { text: '命令参考', link: '/reference/commands' },
      { text: 'GitHub', link: 'https://github.com/xiaou61/project-lifecycle' },
    ],
    sidebar: {
      '/guide/': [
        {
          text: '上手教程',
          items: [
            { text: '开始使用', link: '/guide/getting-started' },
            { text: '全流程教程', link: '/guide/full-workflow' },
            { text: '跨会话恢复与接力', link: '/guide/resume' },
            { text: '需求、来源与验收', link: '/guide/requirements' },
            { text: '需求深挖访谈', link: '/guide/requirements-interview' },
          ],
        },
      ],
      '/reference/': [
        {
          text: '参考',
          items: [
            { text: '总索引', link: '/reference/' },
            { text: '命令参考', link: '/reference/commands' },
            { text: '边界与常见问题', link: '/reference/boundaries' },
          ],
        },
      ],
    },
    outline: { level: [2, 3] },
    search: { provider: 'local' },
    lastUpdated: true,
    footer: {
      message: '事实写入项目工件，聊天只负责推进当前动作。',
      copyright: 'Project Lifecycle',
    },
  },
})
