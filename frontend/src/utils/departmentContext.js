/**
 * JanSakshi Municipal Department Context & Normalization
 * Standardized mapping, lookup, and state synchronization across all 6 divisions.
 */

export const DEPARTMENTS = [
  {
    id: 1,
    code: 'RPW',
    altCodes: ['RPW', 'ROADS'],
    name: 'Roads & Public Works',
    shortName: 'Roads & Works',
    description: 'Road damage, potholes, asphalt resurfacing, curb repairs & footpath safety.',
    slaDays: 7,
    accentColor: '#F36B21',
    heroImage: '/assets/dept_rpw.jpg'
  },
  {
    id: 2,
    code: 'SWM',
    altCodes: ['SWM', 'SANITATION'],
    name: 'Sanitation & Waste Management',
    shortName: 'Sanitation & Waste',
    description: 'Garbage accumulation, overflowing municipal bins, street sweeping & dump clearances.',
    slaDays: 3,
    accentColor: '#16A34A',
    heroImage: '/assets/dept_swm.jpg'
  },
  {
    id: 3,
    code: 'WSS',
    altCodes: ['WSS', 'WSD', 'WATER'],
    dbCode: 'WSD',
    name: 'Water Supply & Sewerage',
    shortName: 'Water & Sewerage',
    description: 'Pipeline bursts, water leakage, contaminated supply, valve pressure & sewer unclogging.',
    slaDays: 5,
    accentColor: '#0284C7',
    heroImage: '/assets/dept_wss.jpg'
  },
  {
    id: 4,
    code: 'DRN',
    altCodes: ['DRN', 'DRAINAGE'],
    name: 'Storm Water Drainage',
    shortName: 'Drainage & Stormwater',
    description: 'Drainage overflow, clogged stormwater canals, desilting, culverts & monsoon flood relief.',
    slaDays: 4,
    accentColor: '#0D9488',
    heroImage: '/assets/dept_drn.jpg'
  },
  {
    id: 5,
    code: 'ESM',
    altCodes: ['ESM', 'ELECTRICAL'],
    name: 'Electrical & Street Lighting',
    shortName: 'Electrical & Lights',
    description: 'Non-functional streetlights, broken electrical poles, exposed wires & dark junction hazard.',
    slaDays: 2,
    accentColor: '#D97706',
    heroImage: '/assets/dept_esm.jpg'
  },
  {
    id: 6,
    code: 'PID',
    altCodes: ['PID', 'PARKS'],
    name: 'Public Infrastructure & Parks',
    shortName: 'Parks & Public Infra',
    description: 'Damaged public parks, broken benches, vandalized amenities, public restrooms & bus shelters.',
    slaDays: 10,
    accentColor: '#7C3AED',
    heroImage: '/assets/dept_pid.jpg'
  }
]

export const DEPARTMENT_MAP_BY_ID = Object.fromEntries(
  DEPARTMENTS.map(d => [d.id, d])
)

/**
 * Robust department resolver that handles:
 * - Numeric ID: 1, 2, 3, 4, 5, 6
 * - Numeric string: "1", "2", "3", "4", "5", "6"
 * - Department code: "RPW", "SWM", "WSS", "WSD", "DRN", "ESM", "PID"
 * - Fallbacks to user's assigned department or RPW
 */
export function resolveDepartment(input, user = null) {
  if (input !== undefined && input !== null && input !== '') {
    const rawStr = String(input).trim().toUpperCase()

    // 1. Try numeric ID
    const num = parseInt(rawStr, 10)
    if (!isNaN(num) && DEPARTMENT_MAP_BY_ID[num]) {
      return DEPARTMENT_MAP_BY_ID[num]
    }

    // 2. Try code / alt codes
    const byCode = DEPARTMENTS.find(d =>
      d.code === rawStr ||
      (d.dbCode && d.dbCode === rawStr) ||
      d.altCodes.includes(rawStr)
    )
    if (byCode) return byCode
  }

  // 3. Fallback to user department if present
  if (user?.department_id && DEPARTMENT_MAP_BY_ID[user.department_id]) {
    return DEPARTMENT_MAP_BY_ID[user.department_id]
  }

  if (user?.department_code) {
    const code = user.department_code.trim().toUpperCase()
    const byCode = DEPARTMENTS.find(d =>
      d.code === code ||
      (d.dbCode && d.dbCode === code) ||
      d.altCodes.includes(code)
    )
    if (byCode) return byCode
  }

  // 4. Default to Roads & Public Works (id 1)
  return DEPARTMENT_MAP_BY_ID[1]
}

/**
 * Synchronize resolved department with localStorage and return normalized config
 */
export function saveDepartmentContext(dept) {
  if (!dept) return
  localStorage.setItem('jansakshi_active_dept_id', dept.id.toString())
  localStorage.setItem('jansakshi_active_dept_code', dept.code)
  localStorage.setItem('jansakshi_active_dept_name', dept.name)
}

/**
 * Retrieve active department from localStorage or user context
 */
export function getActiveDepartment(user = null, queryParam = null) {
  if (queryParam) {
    const resolved = resolveDepartment(queryParam, user)
    saveDepartmentContext(resolved)
    return resolved
  }

  const storedId = localStorage.getItem('jansakshi_active_dept_id')
  const storedCode = localStorage.getItem('jansakshi_active_dept_code')

  if (storedId) {
    const resolved = resolveDepartment(storedId, user)
    return resolved
  }

  if (storedCode) {
    const resolved = resolveDepartment(storedCode, user)
    return resolved
  }

  const defaultDept = resolveDepartment(null, user)
  saveDepartmentContext(defaultDept)
  return defaultDept
}

