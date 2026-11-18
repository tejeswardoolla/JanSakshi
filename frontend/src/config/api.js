/**
 * JanSakshi Centralized API Configuration
 *
 * Resolves API endpoints dynamically based on the execution environment:
 * - Production / Same-Domain Serverless: Defaults to relative path '' (e.g. '/api/...')
 * - Development: Proxied by Vite dev server to local backend, or overridden by VITE_API_BASE_URL
 * - Custom Backend Host: Set VITE_API_BASE_URL in environment (e.g. 'https://api.jansakshi.in')
 */

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')

/**
 * Builds a normalized, fully qualified or relative URL for any API endpoint.
 * Handles existing protocol prefixes (http://, https://) and leading slashes safely.
 * Strips obsolete hardcoded 127.0.0.1:8000 and localhost:8000 prefixes if passed.
 *
 * @param {string} endpoint - API route path (e.g. '/api/authority/me')
 * @returns {string} - Resolved URL
 */
export function getApiUrl(endpoint = '') {
  if (!endpoint) return API_BASE_URL || ''

  // Normalize legacy localhost / 127.0.0.1 development URLs
  let cleanEndpoint = endpoint
  if (typeof cleanEndpoint === 'string') {
    if (cleanEndpoint.startsWith('http://127.0.0.1:8000')) {
      cleanEndpoint = cleanEndpoint.replace('http://127.0.0.1:8000', '')
    } else if (cleanEndpoint.startsWith('http://localhost:8000')) {
      cleanEndpoint = cleanEndpoint.replace('http://localhost:8000', '')
    } else if (cleanEndpoint.startsWith('http://') || cleanEndpoint.startsWith('https://')) {
      // Other absolute external URLs (e.g. public CDN or cloud storage)
      return cleanEndpoint
    }
  }

  if (!cleanEndpoint.startsWith('/')) {
    cleanEndpoint = `/${cleanEndpoint}`
  }

  return API_BASE_URL ? `${API_BASE_URL}${cleanEndpoint}` : cleanEndpoint
}

export default {
  API_BASE_URL,
  getApiUrl,
}
