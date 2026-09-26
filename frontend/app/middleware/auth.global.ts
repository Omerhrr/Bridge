/** Every page except /login requires a signed-in user. */
export default defineNuxtRouteMiddleware(async (to) => {
  if (to.path === '/login') return
  const token = useAuthToken()
  if (!token.value) {
    return navigateTo({ path: '/login', query: to.fullPath !== '/' ? { next: to.fullPath } : {} })
  }
  const { user, fetchUser } = useAuth()
  if (!user.value) {
    await fetchUser()
    if (!user.value) {
      return navigateTo({ path: '/login', query: { next: to.fullPath } })
    }
  }
})
