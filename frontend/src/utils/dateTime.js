/**
 * JanSakshi Centralized Date/Time & Timezone Utility
 * 
 * Standard:
 * - Storage & Backend: UTC (with explicit 'Z' or offset)
 * - Application-wide Display: Asia/Kolkata (Indian Standard Time, IST = UTC+05:30)
 * 
 * Edge cases handled:
 * - ISO strings with 'Z' suffix (e.g. 2026-11-07T06:36:57Z)
 * - ISO strings with explicit timezone offsets (e.g. 2026-11-07T12:06:57+05:30)
 * - ISO strings without offset (treated safely as UTC, never assuming local machine time)
 * - Javascript Date objects and millisecond timestamps
 * - Null, undefined, empty, or malformed values
 * - Midnight crossings, month-end, and year-end boundary transitions
 * - Independent of client/browser's local operating system timezone
 */

export const IST_TIMEZONE = 'Asia/Kolkata'

/**
 * Parses any incoming timestamp representation into a clean Javascript Date object.
 * If the input is a naive ISO string lacking a timezone indicator, it explicitly
 * appends 'Z' to treat it as UTC, preventing the browser from misinterpreting it as local time.
 * 
 * @param {string|number|Date|null|undefined} timestampInput 
 * @returns {Date|null}
 */
export function parseToDate(timestampInput) {
  if (!timestampInput) return null

  if (timestampInput instanceof Date) {
    return isNaN(timestampInput.getTime()) ? null : timestampInput
  }

  if (typeof timestampInput === 'number') {
    const d = new Date(timestampInput)
    return isNaN(d.getTime()) ? null : d
  }

  if (typeof timestampInput === 'string') {
    const trimmed = timestampInput.trim()
    if (!trimmed) return null

    // If it's an ISO format without offset/Z, e.g. "2026-11-07T06:36:57.123" or "2026-11-07 06:36:57"
    // Normalize space to 'T'
    let normalized = trimmed.replace(' ', 'T')

    // If no timezone designator (Z or +hh:mm or -hh:mm) at the end, append 'Z'
    const hasTimezone = /([zZ]|([+-]\d{2}(:?\d{2})?))$/.test(normalized)
    if (!hasTimezone) {
      normalized = normalized + 'Z'
    }

    const d = new Date(normalized)
    return isNaN(d.getTime()) ? null : d
  }

  return null
}

/**
 * Format a timestamp into standard Indian Standard Time (IST) display.
 * Example: "07 Nov 2026, 12:06 PM IST"
 * 
 * @param {string|number|Date|null|undefined} timestamp 
 * @param {Object} options Custom options for Intl.DateTimeFormat
 * @returns {string} Formatted IST date and time
 */
export function formatToIST(timestamp, options = {}) {
  const dateObj = parseToDate(timestamp)
  if (!dateObj) {
    return 'N/A'
  }

  const defaultOptions = {
    timeZone: IST_TIMEZONE,
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
    ...options
  }

  try {
    const formatted = new Intl.DateTimeFormat('en-IN', defaultOptions).format(dateObj)
    return `${formatted} IST`
  } catch (err) {
    console.error('Error formatting date to IST:', err)
    return 'Invalid Date'
  }
}

/**
 * Format date-only in IST.
 * Example: "07 Nov 2026"
 */
export function formatISTDateOnly(timestamp) {
  const dateObj = parseToDate(timestamp)
  if (!dateObj) return 'N/A'

  return new Intl.DateTimeFormat('en-IN', {
    timeZone: IST_TIMEZONE,
    day: '2-digit',
    month: 'short',
    year: 'numeric'
  }).format(dateObj)
}

/**
 * Format time-only in IST.
 * Example: "12:06 PM IST"
 */
export function formatISTTimeOnly(timestamp) {
  const dateObj = parseToDate(timestamp)
  if (!dateObj) return 'N/A'

  const formatted = new Intl.DateTimeFormat('en-IN', {
    timeZone: IST_TIMEZONE,
    hour: '2-digit',
    minute: '2-digit',
    hour12: true
  }).format(dateObj)

  return `${formatted} IST`
}

/**
 * Format full verbose date & time in IST for official reports & receipts.
 * Example: "Saturday, 07 November 2026, 12:06:57 PM IST"
 */
export function formatISTVerbose(timestamp) {
  const dateObj = parseToDate(timestamp)
  if (!dateObj) return 'N/A'

  const formatted = new Intl.DateTimeFormat('en-IN', {
    timeZone: IST_TIMEZONE,
    weekday: 'long',
    day: '2-digit',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true
  }).format(dateObj)

  return `${formatted} IST`
}

