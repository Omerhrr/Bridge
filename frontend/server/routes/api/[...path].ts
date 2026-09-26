/** Server-side API proxy (runtime-configurable).
 *
 * The client always calls same-origin `/api/v1/...`; this nitro route
 * forwards it to the FastAPI backend. The target comes from the
 * NUXT_API_TARGET runtime env var (default http://localhost:8000), so the
 * same build works on Render, Docker or locally without rebuilding.
 *
 * This also keeps the PWA story simple: the service worker caches
 * same-origin /api GETs, and no CORS configuration is needed.
 */
import { proxyRequest } from 'h3'

export default defineEventHandler((event) => {
  const config = useRuntimeConfig(event)
  const target = (config.apiTarget as string || 'http://localhost:8000').replace(/\/+$/, '')
  return proxyRequest(event, `${target}${event.path}`)
})
