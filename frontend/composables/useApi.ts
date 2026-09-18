/** Thin API client: same-origin /api via Nuxt dev proxy (or NUXT_PUBLIC_API_BASE). */

export function useApi() {
  const config = useRuntimeConfig();
  const base = config.public.apiBase || "";

  async function get<T>(path: string, query?: Record<string, unknown>): Promise<T> {
    return $fetch<T>(`${base}${path}`, { query });
  }

  async function post<T>(path: string, body?: unknown): Promise<T> {
    return $fetch<T>(`${base}${path}`, { method: "POST", body });
  }

  async function put<T>(path: string, body?: unknown): Promise<T> {
    return $fetch<T>(`${base}${path}`, { method: "PUT", body });
  }

  async function del(path: string): Promise<void> {
    await $fetch(`${base}${path}`, { method: "DELETE" });
  }

  return { get, post, put, del };
}
