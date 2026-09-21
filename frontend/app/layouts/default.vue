<script setup lang="ts">
const route = useRoute()

const navigation = [
  { label: 'Dashboard', to: '/', icon: 'layout-dashboard' },
  { label: 'Workflows', to: '/workflows', icon: 'workflow' },
  { label: 'Conversations', to: '/conversations', icon: 'messages-square' },
  { label: 'Runs', to: '/runs', icon: 'list-checks' },
  { label: 'Settings', to: '/settings', icon: 'settings' },
]
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <!-- Top navigation (spec section 19: status visible immediately) -->
    <header class="bg-navy text-white">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 h-14 flex items-center gap-6">
        <NuxtLink to="/" class="flex items-center gap-2 shrink-0">
          <span class="grid place-items-center w-7 h-7 rounded-md bg-signal">
            <span class="block w-2.5 h-2.5 rounded-full bg-comms animate-pulse" />
          </span>
          <span class="text-lg font-semibold tracking-tight">Bridge</span>
          <span class="hidden sm:inline text-[10px] uppercase tracking-widest text-white/40 mt-1">communication</span>
        </NuxtLink>

        <nav class="flex items-center gap-1 overflow-x-auto thin-scroll">
          <NuxtLink
            v-for="item in navigation"
            :key="item.to"
            :to="item.to"
            class="px-3 h-9 inline-flex items-center rounded-md text-sm text-white/70 hover:text-white hover:bg-white/10 transition-colors whitespace-nowrap"
            :class="{ 'bg-white/10 text-white': route.path === item.to || (item.to !== '/' && route.path.startsWith(item.to)) }"
          >
            {{ item.label }}
          </NuxtLink>
        </nav>

        <div class="ml-auto hidden md:flex items-center gap-2 text-sm">
          <span class="relative flex h-2 w-2">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-60" />
            <span class="relative inline-flex rounded-full h-2 w-2 bg-success" />
          </span>
          <span class="text-white/70">Status: OK</span>
        </div>
      </div>
    </header>

    <main class="flex-1 mx-auto w-full max-w-7xl px-4 sm:px-6 py-6">
      <slot />
    </main>

    <footer class="border-t border-line bg-surface">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 h-12 flex items-center justify-between text-xs text-muted mt-auto">
        <span>Bridge — communication across language and connectivity barriers</span>
        <span class="hidden sm:inline">FastAPI · Nuxt · Vue Flow · Africa's Talking</span>
      </div>
    </footer>
  </div>
</template>
