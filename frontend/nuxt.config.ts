// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  devtools: { enabled: false },

  // Proxy /api calls to the FastAPI backend during development,
  // so the frontend code can simply call `/api/...`.
  routeRules: {
    "/api/**": { proxy: "http://localhost:8000/api/**" },
  },

  runtimeConfig: {
    public: {
      // Override in production with NUXT_PUBLIC_API_BASE.
      apiBase: "",
    },
  },

  compatibilityDate: "2024-11-01",
});
