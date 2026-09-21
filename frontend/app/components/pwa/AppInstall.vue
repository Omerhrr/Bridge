<script setup lang="ts">
import { Download, Share, X, Smartphone, CheckCircle2 } from 'lucide-vue-next'

/** PWA install experience.
 *
 * variant="banner": floating prompt shown once the browser fires
 *   beforeinstallprompt (Android/desktop Chromium). Dismissible.
 * variant="card": embeddable Settings section with install status, including
 *   iOS Safari instructions (iOS has no programmatic install prompt).
 */
const props = defineProps<{ variant?: 'banner' | 'card' }>()

const canInstall = ref(false)
const installed = ref(false)
const isIOS = ref(false)
const dismissed = ref(false)
let deferred: any = null

onMounted(() => {
  const nav: any = navigator
  installed.value =
    window.matchMedia('(display-mode: standalone)').matches || nav.standalone === true
  isIOS.value = /iphone|ipad|ipod/i.test(navigator.userAgent)
  window.addEventListener('beforeinstallprompt', (event: any) => {
    event.preventDefault()
    deferred = event
    canInstall.value = true
  })
  window.addEventListener('appinstalled', () => {
    installed.value = true
    canInstall.value = false
  })
})

async function install() {
  if (!deferred) return
  deferred.prompt()
  const { outcome } = await deferred.userChoice
  if (outcome === 'accepted') {
    installed.value = true
    canInstall.value = false
  }
  deferred = null
}

const showBanner = computed(
  () => props.variant !== 'card' && canInstall.value && !dismissed.value && !installed.value,
)
</script>

<template>
  <!-- Floating banner -->
  <div v-if="showBanner" class="pwa-banner card shadow-lg p-3 flex items-center gap-3">
    <span class="grid place-items-center w-10 h-10 rounded-lg bg-navy text-white shrink-0">
      <Smartphone class="w-5 h-5" :stroke-width="1.8" />
    </span>
    <div class="min-w-0 flex-1">
      <p class="text-sm font-semibold leading-tight">Install Bridge</p>
      <p class="text-xs text-muted leading-snug mt-0.5">Full-screen and offline-ready, right from your home screen.</p>
    </div>
    <button class="btn-primary shrink-0" @click="install">
      <Download class="w-4 h-4" :stroke-width="1.8" /> Install
    </button>
    <button class="btn-ghost h-8 w-8 px-0 shrink-0" aria-label="Dismiss" @click="dismissed = true">
      <X class="w-4 h-4" :stroke-width="2" />
    </button>
  </div>

  <!-- Settings card -->
  <section v-if="variant === 'card'" class="card p-5">
    <div class="flex items-center gap-2.5 mb-3">
      <span class="grid place-items-center w-9 h-9 rounded-md bg-comms-soft text-comms">
        <Smartphone class="w-4.5 h-4.5" :stroke-width="1.8" />
      </span>
      <div>
        <h2 class="text-sm font-semibold">Install as app</h2>
        <p class="text-xs text-muted">Bridge is a Progressive Web App — installable on phones, tablets and desktops</p>
      </div>
      <span v-if="installed" class="pill-success ml-auto">
        <CheckCircle2 class="w-3.5 h-3.5" :stroke-width="2" /> Installed
      </span>
    </div>

    <div v-if="installed" class="text-sm text-muted">
      Bridge is installed on this device and launches from your home screen or app drawer.
    </div>

    <template v-else>
      <button v-if="canInstall" class="btn-primary" @click="install">
        <Download class="w-4 h-4" :stroke-width="1.8" /> Install Bridge on this device
      </button>

      <ol v-else-if="isIOS" class="text-sm text-muted space-y-1.5 list-decimal list-inside">
        <li>Open Bridge in <span class="font-medium text-ink">Safari</span></li>
        <li>Tap the <Share class="inline w-4 h-4 -mt-0.5" :stroke-width="1.8" /> <span class="font-medium text-ink">Share</span> button</li>
        <li>Choose <span class="font-medium text-ink">Add to Home Screen</span>, then tap <span class="font-medium text-ink">Add</span></li>
      </ol>

      <p v-else class="text-sm text-muted">
        Use your browser menu → <span class="font-medium text-ink">Install app</span> (or
        <span class="font-medium text-ink">Add to Home Screen</span>). The banner prompt appears automatically in
        Chromium browsers once Bridge is eligible.
      </p>
    </template>
  </section>
</template>
