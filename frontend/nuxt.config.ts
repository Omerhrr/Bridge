import tailwindcss from '@tailwindcss/vite'

// Bridge frontend (spec sections 15-18).
// Nuxt 4 + Vue 3 + Tailwind 4 + Vue Flow.
// PWA: installable on mobile & desktop, offline-capable shell (see spec section 18
// "mobile mode / desktop mode" and the PWA requirement).
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: false },

  // Bridge is a dashboard/app (no SEO surface) — the SPA shell precaches in the
  // service worker, giving instant loads, offline navigation and installability.
  ssr: false,

  modules: ['@pinia/nuxt', '@vite-pwa/nuxt'],

  css: [
    '~/assets/css/main.css',
    '@vue-flow/core/dist/style.css',
    '@vue-flow/core/dist/theme-default.css',
  ],

  vite: {
    plugins: [tailwindcss()],
    server: {
      // Allow Cloudflare Quick Tunnel hosts, plus the custom tunnel domain,
      // to reach the Vite dev server. Quick Tunnel hostnames are random per
      // run, so that one is scoped to the whole trycloudflare.com domain
      // rather than disabling the check entirely. Local dev-only setting;
      // nuxt build doesn't run a Vite dev server, so `allowedHosts` has no
      // effect in production.
      allowedHosts: ['.trycloudflare.com', 'bridge.rogan.live'],
    },
  },

  build: {
    transpile: ['@vue-flow/core'],
  },

  // Prerender the SPA shell so the service worker can precache it — this
  // makes offline navigation (workbox navigateFallback '/') actually work.
  nitro: {
    prerender: { routes: ['/'] },
  },

  // The client calls same-origin /api/v1 — server/routes/api/[[...path]].ts
  // forwards to the backend at NUXT_API_TARGET (runtime env, no rebuild needed).
  // In dev this replaces the old devProxy; in production it is the API path.
  runtimeConfig: {
    apiTarget: 'http://localhost:8000',
    public: {
      // Optional escape hatch: set to an absolute backend URL to bypass the
      // proxy entirely (e.g. 'https://bridge-api.onrender.com/api/v1').
      apiBase: '',
    },
  },

  pwa: {
    registerType: 'autoUpdate',
    includeAssets: ['favicon.svg', 'favicon.ico', 'icons/apple-touch-icon.png'],
    manifest: {
      id: '/',
      name: 'Bridge — Communication without barriers',
      short_name: 'Bridge',
      description:
        'Visual communication automation: build voice, SMS and USSD workflows with AI translation so people can communicate across language and connectivity barriers.',
      lang: 'en',
      theme_color: '#0b1220',
      background_color: '#f8fafc',
      display: 'standalone',
      orientation: 'any',
      start_url: '/',
      icons: [
        { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png' },
        { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png' },
        { src: 'icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
      ],
    },
    workbox: {
      globPatterns: ['**/*.{js,css,html,svg,png,ico,woff,woff2}'],
      navigateFallback: '/',
      navigateFallbackDenylist: [/^\/api\//],
      runtimeCaching: [
        {
          // Network-first for API reads so the dashboard still opens on flaky
          // connections (spec section 18: limited-connectivity audiences).
          urlPattern: ({ url }: { url: URL }) => url.pathname.startsWith('/api/'),
          handler: 'NetworkFirst',
          method: 'GET',
          options: {
            cacheName: 'bridge-api-cache',
            networkTimeoutSeconds: 5,
            expiration: { maxEntries: 100, maxAgeSeconds: 600 },
            cacheableResponse: { statuses: [0, 200] },
          },
        },
      ],
    },
    // We render our own install UI (PwaAppInstall) instead of the module default.
    client: { installPrompt: false },
    devOptions: { enabled: false },
  },

  app: {
    head: {
      title: 'Bridge — Communication without barriers',
      htmlAttrs: { lang: 'en' },
      meta: [
        { name: 'viewport', content: 'width=device-width, initial-scale=1, viewport-fit=cover' },
        {
          name: 'description',
          content:
            'Bridge is a visual communication automation platform that uses telecommunications and AI to connect people across language and connectivity barriers.',
        },
        { name: 'theme-color', content: '#0b1220' },
        { name: 'mobile-web-app-capable', content: 'yes' },
        { name: 'apple-mobile-web-app-capable', content: 'yes' },
        { name: 'apple-mobile-web-app-status-bar-style', content: 'black-translucent' },
        { name: 'apple-mobile-web-app-title', content: 'Bridge' },
      ],
      link: [
        { rel: 'manifest', href: '/manifest.webmanifest' },
        { rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' },
        { rel: 'icon', type: 'image/x-icon', href: '/favicon.ico' },
        { rel: 'apple-touch-icon', href: '/icons/apple-touch-icon.png' },
      ],
    },
  },
})
