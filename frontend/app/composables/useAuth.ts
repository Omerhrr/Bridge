/** Session handling: bearer token in a cookie, current user in shared state. */
export interface AuthUser {
  id: number
  email: string
  full_name: string
}

export interface SetupStatus {
  needs_setup: boolean
  setup_code_required: boolean
  registration_open: boolean
  auth_enabled: boolean
}

export function useAuthToken() {
  return useCookie<string | null>('bridge_token', {
    maxAge: 60 * 60 * 24,
    sameSite: 'lax',
    secure: import.meta.client ? location.protocol === 'https:' : true,
  })
}

export function useAuth() {
  const token = useAuthToken()
  const user = useState<AuthUser | null>('bridge-user', () => null)
  const api = useApi()

  async function fetchUser() {
    if (!token.value) {
      user.value = null
      return null
    }
    try {
      user.value = await api<AuthUser>('/auth/me')
    } catch {
      user.value = null
    }
    return user.value
  }

  async function login(email: string, password: string) {
    const body = new URLSearchParams({ username: email, password })
    const res = await api<{ access_token: string; user: AuthUser }>('/auth/login', {
      method: 'POST',
      body,
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    token.value = res.access_token
    user.value = res.user
  }

  async function register(payload: { email: string; password: string; full_name: string; setup_code?: string }) {
    const res = await api<{ access_token: string; user: AuthUser }>('/auth/register', {
      method: 'POST',
      body: payload,
    })
    token.value = res.access_token
    user.value = res.user
  }

  function logout() {
    token.value = null
    user.value = null
    return navigateTo('/login')
  }

  return { token, user, fetchUser, login, register, logout }
}
