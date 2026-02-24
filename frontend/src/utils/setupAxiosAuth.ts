import axios, { AxiosError, AxiosHeaders, InternalAxiosRequestConfig } from 'axios'
import { getApiBaseUrl } from '../config'
import { api } from '../api/client'

type RetryableConfig = InternalAxiosRequestConfig & { _retry?: boolean }

let initialized = false
let isRefreshing = false
let subscribers: Array<(token: string | null) => void> = []

const getRefreshEndpoint = (): string => {
  const base = getApiBaseUrl()
  return base ? `${base}/api/auth/refresh` : '/api/auth/refresh'
}

const notifySubscribers = (token: string | null) => {
  subscribers.forEach((cb) => cb(token))
  subscribers = []
}

const requestNewAccessToken = async (): Promise<string | null> => {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) return null

  try {
    const response = await axios.post(
      getRefreshEndpoint(),
      null,
      {
        params: { refresh_token: refreshToken },
        timeout: 15000,
      }
    )
    const newAccessToken = response.data?.access_token as string | undefined
    const newRefreshToken = response.data?.refresh_token as string | undefined
    if (!newAccessToken) return null

    localStorage.setItem('access_token', newAccessToken)
    if (newRefreshToken) {
      localStorage.setItem('refresh_token', newRefreshToken)
    }
    return newAccessToken
  } catch {
    return null
  }
}

const withAuthHeaders = (config: InternalAxiosRequestConfig): InternalAxiosRequestConfig => {
  const token = localStorage.getItem('access_token')
  if (!token) return config

  const headers = AxiosHeaders.from(config.headers)
  if (!headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  config.headers = headers
  return config
}

const shouldSkipRefresh = (url?: string): boolean => {
  const target = url || ''
  return target.includes('/api/auth/signin') || target.includes('/api/auth/signup') || target.includes('/api/auth/refresh')
}

const withRefreshRetry = async (error: AxiosError): Promise<any> => {
  const responseStatus = error.response?.status
  const originalConfig = error.config as RetryableConfig | undefined
  if (!originalConfig || responseStatus !== 401 || originalConfig._retry || shouldSkipRefresh(originalConfig.url)) {
    return Promise.reject(error)
  }

  originalConfig._retry = true

  if (isRefreshing) {
    return new Promise((resolve, reject) => {
      subscribers.push((token) => {
        if (!token) {
          reject(error)
          return
        }
        const headers = AxiosHeaders.from(originalConfig.headers)
        headers.set('Authorization', `Bearer ${token}`)
        originalConfig.headers = headers
        resolve(axios(originalConfig))
      })
    })
  }

  isRefreshing = true
  const refreshedToken = await requestNewAccessToken()
  isRefreshing = false
  notifySubscribers(refreshedToken)

  if (!refreshedToken) {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    return Promise.reject(error)
  }

  const headers = AxiosHeaders.from(originalConfig.headers)
  headers.set('Authorization', `Bearer ${refreshedToken}`)
  originalConfig.headers = headers
  return axios(originalConfig)
}

export const setupAxiosAuth = () => {
  if (initialized) return
  initialized = true

  api.interceptors.request.use(withAuthHeaders)
  api.interceptors.response.use(
    (response) => response,
    (error) => withRefreshRetry(error)
  )

  axios.interceptors.request.use(withAuthHeaders)
  axios.interceptors.response.use(
    (response) => response,
    (error) => withRefreshRetry(error)
  )
}
