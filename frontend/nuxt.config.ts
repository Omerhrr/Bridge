import tailwindcss from '@tailwindcss/vite'

// Bridge frontend (spec sections 15-18).
// Nuxt 4 + Vue 3 + Tailwind 4 + Vue Flow.
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: false },

  modules: ['@pinia/nuxt'],

  css: [
    '~/assets/css/main.css',
    '@vue-flow/core/dist/style.css',
    '@vue-flow/core/dist/theme-default.css',
  ],

  vite: {
    plugins: [tailwindcss()],
  },

  build: {
    transpile: ['@vue-flow/core'],
  },

  // Local development proxy: the Nuxt dev server forwards /api to FastAPI.
  // In production (Render) set NUXT_PUBLIC_API_BASE to the backend URL.
  nitro: {
    devProxy: {
      '/api': { target: 'http://localhost:8000/api', changeOrigin: true },
    },
  },

  runtimeConfig: {
    public: {
      apiBase: '',
    },
  },

  app: {
    head: {
      title: 'Bridge — Communication without barriers',
      htmlAttrs: { lang: 'en' },
      meta: [
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        {
          name: 'description',
          content:
            'Bridge is a visual communication automation platform that uses telecommunications and AI to connect people across language and connectivity barriers.',
        },
      ],
    },
  },
})
