import React, { createContext, useContext, useState, useEffect, useRef } from 'react'
import { getApiUrl } from '../config/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('jansakshi_authority_token') || null)
  const [refreshToken, setRefreshToken] = useState(() => localStorage.getItem('jansakshi_authority_refresh_token') || null)
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem('jansakshi_authority_user')
      return saved ? JSON.parse(saved) : null
    } catch (e) {
      return null
    }
  })

  const [loading, setLoading] = useState(false)
  const isRefreshingRef = useRef(false)

  const login = async (username, password) => {
    setLoading(true)
    try {
      const res = await fetch(getApiUrl('/api/auth/login'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      })

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Authentication failed. Please verify credentials.')
      }

      const data = await res.json()
      setToken(data.access_token)
      localStorage.setItem('jansakshi_authority_token', data.access_token)

      if (data.refresh_token) {
        setRefreshToken(data.refresh_token)
        localStorage.setItem('jansakshi_authority_refresh_token', data.refresh_token)
      }

      setUser(data.user)
      localStorage.setItem('jansakshi_authority_user', JSON.stringify(data.user))
      return { success: true, user: data.user }
    } catch (err) {
      return { success: false, error: err.message }
    } finally {
      setLoading(false)
    }
  }

  const loginJudgeDemo = async (role) => {
    setLoading(true)
    try {
      const res = await fetch(getApiUrl(`/api/auth/judge-demo/${role}`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Judge demo authentication failed.')
      }

      const data = await res.json()
      setToken(data.access_token)
      localStorage.setItem('jansakshi_authority_token', data.access_token)

      if (data.refresh_token) {
        setRefreshToken(data.refresh_token)
        localStorage.setItem('jansakshi_authority_refresh_token', data.refresh_token)
      }

      setUser(data.user)
      localStorage.setItem('jansakshi_authority_user', JSON.stringify(data.user))
      return { success: true, user: data.user }
    } catch (err) {
      return { success: false, error: err.message }
    } finally {
      setLoading(false)
    }
  }

  const logout = async () => {
    const curToken = token || localStorage.getItem('jansakshi_authority_token')
    const curRefreshToken = refreshToken || localStorage.getItem('jansakshi_authority_refresh_token')

    // Server-enforced revocation (fire-and-forget)
    if (curToken || curRefreshToken) {
      try {
        fetch(getApiUrl('/api/auth/logout'), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: curToken ? `Bearer ${curToken}` : ''
          },
          body: JSON.stringify({ refresh_token: curRefreshToken })
        }).catch(() => {})
      } catch (e) {}
    }

    setToken(null)
    setRefreshToken(null)
    setUser(null)
    localStorage.removeItem('jansakshi_authority_token')
    localStorage.removeItem('jansakshi_authority_refresh_token')
    localStorage.removeItem('jansakshi_authority_user')
  }

  const trySilentRefresh = async () => {
    const savedRefreshToken = refreshToken || localStorage.getItem('jansakshi_authority_refresh_token')
    if (!savedRefreshToken || isRefreshingRef.current) {
      return null
    }

    isRefreshingRef.current = true
    try {
      const res = await fetch(getApiUrl('/api/auth/refresh'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: savedRefreshToken })
      })

      if (res.ok) {
        const data = await res.json()
        setToken(data.access_token)
        localStorage.setItem('jansakshi_authority_token', data.access_token)
        if (data.refresh_token) {
          setRefreshToken(data.refresh_token)
          localStorage.setItem('jansakshi_authority_refresh_token', data.refresh_token)
        }
        return data.access_token
      }
      return null
    } catch (e) {
      return null
    } finally {
      isRefreshingRef.current = false
    }
  }

  const authFetch = async (url, options = {}) => {
    const resolvedUrl = typeof url === 'string' ? getApiUrl(url) : url
    const currentToken = token || localStorage.getItem('jansakshi_authority_token')
    const headers = {
      ...(options.headers || {}),
      Authorization: currentToken ? `Bearer ${currentToken}` : ''
    }

    const res = await fetch(resolvedUrl, { ...options, headers })

    if (res.status === 401) {
      // Don't loop if the failing request was itself a login or refresh
      const isAuthUrl = typeof url === 'string' && (url.includes('/api/auth/refresh') || url.includes('/api/auth/login'))
      if (!isAuthUrl) {
        // Attempt transparent token refresh
        const refreshedToken = await trySilentRefresh()
        if (refreshedToken) {
          const retryHeaders = {
            ...(options.headers || {}),
            Authorization: `Bearer ${refreshedToken}`
          }
          const retryRes = await fetch(resolvedUrl, { ...options, headers: retryHeaders })
          if (retryRes.status !== 401) {
            return retryRes
          }
        }
      }

      // If refresh failed or was not possible, perform clean logout and redirect
      await logout()
      if (typeof window !== 'undefined' && window.location.pathname.startsWith('/authority') && !window.location.pathname.includes('/login')) {
        window.location.href = '/authority/login?session_expired=true'
      }
    }

    return res
  }

  return (
    <AuthContext.Provider value={{ token, refreshToken, user, isAuthenticated: !!token, loading, login, loginJudgeDemo, logout, authFetch }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

