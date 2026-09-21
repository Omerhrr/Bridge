/** Utility helpers shared across pages. */

export function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  const d = new Date(value)
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function formatTime(value?: string | null): string {
  if (!value) return '—'
  const d = new Date(value)
  return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function formatDuration(startedAt?: string | null, finishedAt?: string | null): string {
  if (!startedAt) return '—'
  const end = finishedAt ? new Date(finishedAt).getTime() : Date.now()
  const seconds = (end - new Date(startedAt).getTime()) / 1000
  if (seconds < 1) return `${(seconds * 1000).toFixed(0)}ms`
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`
}

export function maskNumber(number?: string | null): string {
  if (!number) return '—'
  if (number.length <= 6) return number
  return `${number.slice(0, 5)}…${number.slice(-3)}`
}

export function shortId(id?: string | null): string {
  return id ? id.replace(/^run_/, '').slice(0, 8) : '—'
}
