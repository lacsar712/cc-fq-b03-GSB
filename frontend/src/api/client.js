import axios from 'axios'
import { useAuthStore } from '../stores/auth'

const api = axios.create({
  baseURL: '/api',
  timeout: 20000,
})

api.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') {
      err.message = detail
    } else if (Array.isArray(detail)) {
      err.message = detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
    }
    return Promise.reject(err)
  },
)

export async function login(username, password) {
  const { data } = await api.post('/auth/login', { username, password })
  return data
}

export async function getHealth() {
  const { data } = await api.get('/health')
  return data
}

export async function listSamples() {
  const { data } = await api.get('/samples')
  return data
}

export async function listJobs(filters = {}) {
  // 筛选在服务端收缩：status 可多值（重复 query 参数），q 为样例名关键字。
  const params = new URLSearchParams()
  const statuses = Array.isArray(filters.statuses) ? filters.statuses : []
  statuses.forEach((s) => params.append('status', s))
  if (filters.q && filters.q.trim()) {
    params.append('q', filters.q.trim())
  }
  const { data } = await api.get('/jobs', { params })
  return data
}

export async function getJob(id) {
  const { data } = await api.get(`/jobs/${id}`)
  return data
}

export async function getJobStages(id) {
  const { data } = await api.get(`/jobs/${id}/stages`)
  return data
}

export async function createJob(body) {
  const { data } = await api.post('/jobs', body)
  return data
}

export default api
