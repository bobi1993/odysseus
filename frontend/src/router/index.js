import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'Dashboard', component: () => import('../views/DashboardView.vue') },
  { path: '/chat', name: 'Chat', component: () => import('../views/ChatView.vue') },
  { path: '/videos', name: 'Videos', component: () => import('../views/VideosView.vue') },
  { path: '/videos/:id', name: 'Video Detail', component: () => import('../views/VideoDetailView.vue'), props: true },
  { path: '/faces', name: 'Faces', component: () => import('../views/FacesView.vue') },
  { path: '/tasks', name: 'Tasks', component: () => import('../views/TasksView.vue') },
  { path: '/agents', name: 'Agents', component: () => import('../views/AgentsView.vue') },
  { path: '/settings', name: 'Settings', component: () => import('../views/SettingsView.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
