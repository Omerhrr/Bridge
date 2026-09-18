// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  devtools: { enabled: false },

  // Vue Flow powers the workflow builder canvas (spec §20).
  build: {
    transpile: ["@vue-flow/core", "@vue-flow/background"],
  },

  // Proxy API and telecom webhooks to FastAPI during development.
  routeRules: {
    "/api/**": { proxy: "http://localhost:8000/api/**" },
    "/webhooks/**": { proxy: "http://localhost:8000/webhooks/**" },
  },

  runtimeConfig: {
    public: {
      apiBase: "", // override with NUXT_PUBLIC_API_BASE in production
    },
  },

  compatibilityDate: "2024-11-01",
});
