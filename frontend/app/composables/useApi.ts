/** API client.
 *
 * Client-side: uses the Nuxt dev proxy (/api -> FastAPI) in development,
 * or NUXT_PUBLIC_API_BASE in production (Render).
 * Server-side (SSR): relative URLs would hit Nitro's internal router, so
 * we call the backend directly — either the configured absolute apiBase or
 * the local FastAPI port in the sandbox.
 */
export function useApi() {
  const config = useRuntimeConfig()
  const apiBase = (config.public.apiBase as string) || ''

  const baseURL = import.meta.server
    ? apiBase.startsWith('http')
      ? apiBase
      : 'http://localhost:8000/api/v1'
    : apiBase || '/api/v1'

  const client = $fetch.create({
    baseURL,
    retry: 0,
    onResponseError({ response }) {
      // Central error logging; pages handle their own UI state.
      console.error(`[bridge-api] ${response.status} ${response.url}`)
    },
  })

  return client
}
