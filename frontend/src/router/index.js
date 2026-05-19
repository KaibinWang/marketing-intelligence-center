import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'EventList', component: () => import('@/views/EventList.vue') },
  { path: '/event/:id', name: 'EventDetail', component: () => import('@/views/EventDetail.vue') },
  { path: '/stats', name: 'Stats', component: () => import('@/views/Stats.vue') },
  { path: '/sources', name: 'Sources', component: () => import('@/views/Sources.vue') },
  { path: '/pipeline', name: 'Pipeline', component: () => import('@/views/Pipeline.vue') },
  { path: '/push-logs', name: 'PushLogs', component: () => import('@/views/PushLogs.vue') },
  { path: '/settings', name: 'Settings', component: () => import('@/views/Settings.vue') },
  { path: '/crawl/:id', name: 'CrawlDetail', component: () => import('@/views/CrawlDetail.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
