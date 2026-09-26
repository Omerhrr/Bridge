/** API client.
 *
 * The browser always calls same-origin /api/v1 (the Nitro route forwards it
 * to FastAPI), or NUXT_PUBLIC_API_BASE when set. The signed-in user's bearer
 * token is attached to every request; a 401 sends the user to /login.
 */
export function useApi() {
  const config = useRuntimeConfig()
  const apiBase = (config.public.apiBase as string) || ''
  const token = useAuthToken()

  const baseURL = import.meta.server
    ? apiBase.startsWith('http')
      ? apiBase
      : 'http://localhost:8000/api/v1'
    : apiBase || '/api/v1'

  return $fetch.create({
    baseURL,
    retry: 0,
    onRequest({ options }) {
      if (token.value) {
        const headers = new Headers(options.headers as HeadersInit | undefined)
        headers.set('Authorization', `Bearer ${token.value}`)
        options.headers = headers
      }
    },
    onResponseError({ request, response }) {
      console.error(`[bridge-api] ${response.status} ${response.url}`)
      const url = typeof request === 'string' ? request : (request as Request).url
      if (response.status === 401 && !url.includes('/auth/')) {
        token.value = null
        const route = useRoute()
        if (route.path !== '/login') {
          navigateTo({ path: '/login', query: { next: route.fullPath } })
        }
      }
    },
  })
}
