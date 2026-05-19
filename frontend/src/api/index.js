import axios from 'axios'
import dayjs from 'dayjs'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

api.interceptors.response.use(
  res => res.data,
  err => Promise.reject(err.response?.data || err)
)

export function listEvents(params) {
  return api.get('/events', { params })
}

export function getEvent(id) {
  return api.get(`/events/${id}`)
}

export function markSent(id) {
  return api.post(`/events/${id}/mark-sent`)
}

export function clearEvents() {
  return api.post('/events/clear')
}

export function getStats() {
  return api.get('/stats')
}

export function getSources() {
  return api.get('/sources')
}

export function triggerCrawl(source, keywords) {
  return api.post(`/crawl/${source}`, { keywords: keywords || null })
}

export function getCrawlStatus(crawlId) {
  return api.get(`/crawl-status/${crawlId}`)
}

export function cancelCrawl(crawlId) {
  return api.post(`/crawl-cancel/${crawlId}`)
}

export function runPipeline() {
  return api.post('/run-pipeline')
}

export function getPipelineLatest() {
  return api.get('/pipeline-latest')
}

export function getPipelineRuns(limit = 10) {
  return api.get('/pipeline-runs', { params: { limit } })
}

export function getPushLogs(params) {
  return api.get('/push-logs', { params })
}

export function getSettings() {
  return api.get('/settings')
}

export function updateSettings(data) {
  return api.put('/settings', data)
}

export function getCrawlDetail(crawlId) {
  return api.get(`/crawl-status/${crawlId}`)
}

export { dayjs }
