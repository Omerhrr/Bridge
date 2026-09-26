<script setup lang="ts">
import {
  Laptop, Smartphone, Monitor,
  LayoutDashboard, Workflow, MessagesSquare, ListChecks, Settings, Send, Users, BookOpen, LogOut,
} from 'lucide-vue-next'
import type { Component } from 'vue'

const route = useRoute()
// Destructure so the refs become top-level bindings (auto-unwrapped in template)
const { isMobile, pref, init, cycle } = useDeviceMode()
onMounted(() => init())

const navigation = [
  { label: 'Dashboard', to: '/', icon: LayoutDashboard },
  { label: 'Messages', to: '/messages', icon: Send },
  { label: 'Contacts', to: '/contacts', icon: Users },
  { label: 'Knowledge', to: '/knowledge', icon: BookOpen },
  { label: 'Workflows', to: '/workflows', icon: Workflow },
  { label: 'Conversations', to: '/conversations', icon: MessagesSquare },
  { label: 'Runs', to: '/runs', icon: ListChecks },
  { label: 'Settings', to: '/settings', icon: Settings },
]
// The mobile tab bar has room for five destinations.
const mobileNavigation = navigation.filter((item) => !['/conversations', '/runs', '/contacts'].includes(item.to))

const { user, logout } = useAuth()

const modeIcon = computed<Component>(() =>
  pref.value === 'auto' ? Laptop : pref.value === 'mobile' ? Smartphone : Monitor,
)
const modeLabel = computed(() =>
  pref.value === 'auto' ? 'Auto' : pref.value === 'mobile' ? 'Mobile' : 'Desktop',
)

function isActive(to: string) {
  return to === '/' ? route.path === '/' : route.path.startsWith(to)
}
</script>

<template>
  <div class="min-h-dvh flex flex-col" :class="isMobile ? 'mode-mobile' : 'mode-desktop'">
    <!-- Top bar: full navigation on desktop, compact brand bar on mobile (spec section 19) -->
    <header class="bg-navy text-white sticky top-0 z-40">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 h-14 flex items-center gap-4">
        <NuxtLink to="/" class="flex items-center gap-2 shrink-0">
          <span class="grid place-items-center w-7 h-7 rounded-md bg-signal">
            <span class="block w-2.5 h-2.5 rounded-full bg-comms animate-pulse" />
          </span>
          <span class="text-lg font-semibold tracking-tight">Bridge</span>
          <span class="hidden 2xl:inline text-[10px] uppercase tracking-widest text-white/40 mt-1">communication</span>
        </NuxtLink>

        <!-- Desktop navigation -->
        <nav v-if="!isMobile" class="flex items-center gap-1 overflow-x-auto thin-scroll">
          <NuxtLink
            v-for="item in navigation"
            :key="item.to"
            :to="item.to"
            class="px-3 h-9 inline-flex items-center rounded-md text-sm text-white/70 hover:text-white hover:bg-white/10 transition-colors whitespace-nowrap"
            :class="{ 'bg-white/10 text-white': isActive(item.to) }"
          >
            {{ item.label }}
          </NuxtLink>
        </nav>

        <div class="ml-auto flex items-center gap-2">
          <span v-if="!isMobile" class="hidden 2xl:flex items-center gap-2 text-sm whitespace-nowrap">
            <span class="relative flex h-2 w-2">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-60" />
              <span class="relative inline-flex rounded-full h-2 w-2 bg-success" />
            </span>
            <span class="text-white/70">Status: OK</span>
          </span>

          <button
            v-if="user"
            class="h-9 px-2.5 inline-flex items-center gap-1.5 rounded-md hover:bg-white/10 text-sm text-white/80 transition-colors"
            :title="`Signed in as ${user.email}, sign out`"
            @click="logout()"
          >
            <LogOut class="w-4 h-4" :stroke-width="1.8" />
            <span class="hidden 2xl:inline text-xs whitespace-nowrap">{{ user.full_name || user.email }}</span>
          </button>

          <!-- Device mode toggle: Auto → Mobile → Desktop -->
          <button
            class="h-9 px-2.5 inline-flex items-center gap-1.5 rounded-md bg-white/10 hover:bg-white/20 text-sm text-white/90 transition-colors"
            :title="`UI mode: ${modeLabel}, click to switch`"
            @click="cycle()"
          >
            <component :is="modeIcon" class="w-4 h-4" :stroke-width="1.8" />
            <span class="hidden sm:inline text-xs font-medium">{{ modeLabel }}</span>
          </button>
        </div>
      </div>
    </header>

    <main
      class="flex-1 mx-auto w-full max-w-7xl px-4 sm:px-6 py-5"
      :class="isMobile ? 'pb-24' : ''"
    >
      <slot />
    </main>

    <footer v-if="!isMobile" class="border-t border-line bg-surface">
      <div class="mx-auto max-w-7xl px-4 sm:px-6 h-12 flex items-center justify-between text-xs text-muted">
        <span>Bridge: communication across language and connectivity barriers</span>
        <span class="hidden sm:inline">FastAPI · Nuxt · Vue Flow · Africa's Talking</span>
      </div>
    </footer>

    <!-- Mobile bottom tab navigation -->
    <nav v-if="isMobile" class="mobile-bottom-nav" aria-label="Primary">
      <NuxtLink
        v-for="item in mobileNavigation"
        :key="item.to"
        :to="item.to"
        class="tab"
        :class="{ active: isActive(item.to) }"
      >
        <component :is="item.icon" class="w-[22px] h-[22px]" :stroke-width="1.9" />
        <span>{{ item.label }}</span>
      </NuxtLink>
    </nav>

    <!-- PWA install banner (appears when the browser allows installation) -->
    <PwaAppInstall variant="banner" />
  </div>
</template>
