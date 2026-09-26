<script setup lang="ts">
import { reactive, ref } from 'vue'
import { Copy, Check, PhoneCall, BrainCircuit, ShieldCheck, Laptop, Smartphone, Monitor, MessageCircle } from 'lucide-vue-next'
import type { ProviderStatus, WhatsAppConfig } from '~/types'

definePageMeta({ layout: 'default' })

const api = useApi()
const dm = useDeviceMode()
onMounted(() => dm.init())
const status = ref<ProviderStatus | null>(null)
const error = ref('')
const copied = ref('')

const modeOptions = [
  { key: 'auto' as const, icon: Laptop, title: 'Auto', description: 'Follows your screen size: desktop UI on large screens, mobile UI on phones' },
  { key: 'mobile' as const, icon: Smartphone, title: 'Mobile', description: 'Bottom navigation, touch-sized controls, bottom sheets in the builder' },
  { key: 'desktop' as const, icon: Monitor, title: 'Desktop', description: 'Top navigation and the three-column workflow builder, even on small screens' },
]

const webhookUrls = computed(() => {
  if (!import.meta.client) return { voice: '', sms: '', ussd: '' }
  const origin = window.location.origin
  return {
    voice: `${origin}/api/v1/webhooks/africastalking/voice`,
    sms: `${origin}/api/v1/webhooks/africastalking/sms`,
    ussd: `${origin}/api/v1/webhooks/africastalking/ussd`,
  }
})
const whatsappWebhookUrl = computed(() => (import.meta.client ? `${window.location.origin}/api/v1/webhooks/whatsapp` : ''))

onMounted(async () => {
  try {
    status.value = await api<ProviderStatus>('/settings/providers')
  } catch {
    error.value = 'Could not load provider settings.'
  }
  await loadWhatsappConfig()
})

// ------------------------------------------------------- WhatsApp settings
const waConfig = ref<WhatsAppConfig | null>(null)
const waForm = reactive({ phone_number_id: '', verify_token: '', access_token: '' })
const waSaving = ref(false)
const waSaved = ref(false)
const waError = ref('')

async function loadWhatsappConfig() {
  try {
    waConfig.value = await api<WhatsAppConfig>('/settings/whatsapp')
    waForm.phone_number_id = waConfig.value.phone_number_id
    waForm.verify_token = waConfig.value.verify_token
  } catch {
    waError.value = 'Could not load WhatsApp settings.'
  }
}

async function saveWhatsappConfig() {
  waSaving.value = true
  waError.value = ''
  waSaved.value = false
  try {
    waConfig.value = await api<WhatsAppConfig>('/settings/whatsapp', {
      method: 'PUT',
      body: {
        phone_number_id: waForm.phone_number_id.trim(),
        verify_token: waForm.verify_token.trim(),
        // Blank means "keep what's already saved"; only send a real value.
        access_token: waForm.access_token.trim() || null,
      },
    })
    waForm.access_token = ''
    waSaved.value = true
    setTimeout(() => (waSaved.value = false), 2500)
    status.value = await api<ProviderStatus>('/settings/providers')
  } catch (err: any) {
    waError.value = err?.data?.detail || 'Could not save WhatsApp settings.'
  } finally {
    waSaving.value = false
  }
}

async function copy(value: string, key: string) {
  try {
    await navigator.clipboard.writeText(value)
    copied.value = key
    setTimeout(() => (copied.value = ''), 1500)
  } catch {
    /* clipboard unavailable */
  }
}
</script>

<template>
  <div>
    <div class="mb-5">
      <h1 class="text-xl font-semibold tracking-tight">Settings</h1>
      <p class="text-sm text-muted mt-0.5">Device mode, app installation and provider configuration</p>
    </div>

    <p v-if="error" class="card p-4 text-sm text-error bg-error-soft border-error/40 mb-4">{{ error }}</p>

    <!-- Appearance: mobile mode / desktop mode (spec section 18) -->
    <section class="card p-5 mb-4">
      <div class="flex items-center gap-2.5 mb-1">
        <span class="grid place-items-center w-9 h-9 rounded-md bg-signal-soft text-signal">
          <Monitor class="w-4.5 h-4.5" :stroke-width="1.8" />
        </span>
        <div>
          <h2 class="text-sm font-semibold">Appearance</h2>
          <p class="text-xs text-muted">Choose how Bridge presents itself; the setting is saved on this device</p>
        </div>
        <span class="pill-signal ml-auto capitalize">{{ dm.mode.value }} mode active</span>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-3">
        <button
          v-for="option in modeOptions"
          :key="option.key"
          class="text-left p-3 rounded-lg border transition-colors"
          :class="dm.pref.value === option.key ? 'border-signal bg-signal-soft/60 ring-2 ring-signal/20' : 'border-line bg-surface hover:border-signal/40'"
          @click="dm.setPref(option.key)"
        >
          <div class="flex items-center gap-2 mb-1">
            <component :is="option.icon" class="w-4.5 h-4.5" :class="dm.pref.value === option.key ? 'text-signal' : 'text-muted'" :stroke-width="1.8" />
            <span class="text-sm font-semibold">{{ option.title }}</span>
          </div>
          <p class="text-xs text-muted leading-snug">{{ option.description }}</p>
        </button>
      </div>
    </section>

    <!-- Install as PWA -->
    <div class="mb-4">
      <PwaAppInstall variant="card" />
    </div>

    <div v-if="!status" class="card p-6 h-48 animate-pulse" />

    <template v-else>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <!-- Africa's Talking -->
        <section class="card p-5">
          <div class="flex items-center gap-2.5 mb-3">
            <span class="grid place-items-center w-9 h-9 rounded-md bg-signal-soft text-signal">
              <PhoneCall class="w-4.5 h-4.5" :stroke-width="1.8" />
            </span>
            <div>
              <h2 class="text-sm font-semibold">Africa's Talking</h2>
              <p class="text-xs text-muted">Voice · SMS · USSD · Airtime · Webhooks</p>
            </div>
            <span :class="status.telecom.configured ? 'pill-success' : 'pill-warning'" class="ml-auto">
              {{ status.telecom.configured ? 'Connected' : 'Simulated' }}
            </span>
          </div>
          <dl class="text-sm space-y-1.5">
            <div class="flex justify-between gap-4">
              <dt class="text-muted">Provider</dt>
              <dd class="font-medium">{{ status.telecom.provider }}</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="text-muted">Mode</dt>
              <dd class="font-medium">{{ status.telecom.sandbox ? 'Sandbox' : 'Production' }}</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="text-muted">Bridge number</dt>
              <dd class="font-medium tabular-nums">{{ status.telecom.phone_number || 'not set' }}</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="text-muted">Shortcode</dt>
              <dd class="font-medium tabular-nums">{{ status.telecom.shortcode || 'not set' }}</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="text-muted">Sender ID</dt>
              <dd class="font-medium">{{ status.telecom.sender_id || 'not set' }}</dd>
            </div>
          </dl>
          <p class="text-xs text-muted mt-3 leading-relaxed">
            Configure with <code class="bg-canvas px-1 rounded">AT_USERNAME</code>,
            <code class="bg-canvas px-1 rounded">AT_API_KEY</code> and
            <code class="bg-canvas px-1 rounded">AT_SHORTCODE</code> environment variables on the backend.
          </p>
        </section>

        <!-- WhatsApp (Meta Cloud API) -->
        <section class="card p-5 lg:col-span-2">
          <div class="flex items-center gap-2.5 mb-3">
            <span class="grid place-items-center w-9 h-9 rounded-md bg-success-soft text-success">
              <MessageCircle class="w-4.5 h-4.5" :stroke-width="1.8" />
            </span>
            <div>
              <h2 class="text-sm font-semibold">WhatsApp</h2>
              <p class="text-xs text-muted">Meta Cloud API · a second channel alongside SMS · connect your own WhatsApp Business number here</p>
            </div>
            <span :class="status.whatsapp.configured ? 'pill-success' : 'pill-warning'" class="ml-auto">
              {{ status.whatsapp.configured ? 'Connected' : 'Not connected' }}
            </span>
          </div>

          <p v-if="waError" class="text-xs text-error mb-3">{{ waError }}</p>

          <div class="grid gap-4 lg:grid-cols-2">
            <form class="space-y-3" @submit.prevent="saveWhatsappConfig">
              <div>
                <label class="label" for="wa-phone-id">Phone number ID</label>
                <input id="wa-phone-id" v-model="waForm.phone_number_id" class="input font-mono" placeholder="109876543210987">
                <p class="text-[11px] text-muted mt-1">From Meta's developer console: WhatsApp &gt; API Setup &gt; "Phone number ID".</p>
              </div>
              <div>
                <label class="label" for="wa-token">Access token</label>
                <input
                  id="wa-token" v-model="waForm.access_token" type="password" class="input font-mono" autocomplete="off"
                  :placeholder="waConfig?.has_access_token ? 'Saved · leave blank to keep it' : 'EAAG…'"
                >
                <p class="text-[11px] text-muted mt-1">A permanent token from a System User with access to your WhatsApp app. Stored encrypted, never shown again.</p>
              </div>
              <div>
                <label class="label" for="wa-verify">Verify token</label>
                <input id="wa-verify" v-model="waForm.verify_token" class="input font-mono" placeholder="pick any secret string">
                <p class="text-[11px] text-muted mt-1">Made up by you; enter the same value in Meta's webhook setup below.</p>
              </div>
              <div class="flex items-center justify-end gap-2">
                <span v-if="waSaved" class="text-xs text-success">Saved</span>
                <button class="btn-primary" :disabled="waSaving">{{ waSaving ? 'Saving…' : 'Save' }}</button>
              </div>
            </form>

            <div>
              <dl class="text-sm space-y-1.5 mb-3">
                <div class="flex justify-between gap-4">
                  <dt class="text-muted">Phone number ID</dt>
                  <dd class="font-medium tabular-nums">{{ status.whatsapp.phone_number_id || 'not set' }}</dd>
                </div>
              </dl>
              <p class="text-xs font-medium mb-1">Webhook URL</p>
              <div class="flex items-center gap-2">
                <code class="flex-1 text-xs bg-canvas rounded-md px-2.5 py-2 overflow-x-auto thin-scroll whitespace-nowrap">{{ whatsappWebhookUrl }}</code>
                <button class="btn-ghost shrink-0" title="Copy webhook URL" @click="copy(whatsappWebhookUrl, 'whatsapp')">
                  <Check v-if="copied === 'whatsapp'" class="w-4 h-4 text-success" :stroke-width="1.8" />
                  <Copy v-else class="w-4 h-4" :stroke-width="1.8" />
                </button>
              </div>
              <p class="text-xs text-muted mt-3 leading-relaxed">
                In Meta's developer console (WhatsApp &gt; Configuration), set the URL above as the webhook, enter your verify token, and subscribe to the
                <code class="bg-canvas px-1 rounded">messages</code> field. Then build a flow with the "Incoming WhatsApp" trigger and "Send WhatsApp" node in Workflows to reply.
              </p>
            </div>
          </div>
        </section>

        <!-- AI provider -->
        <section class="card p-5">
          <div class="flex items-center gap-2.5 mb-3">
            <span class="grid place-items-center w-9 h-9 rounded-md bg-navy text-white">
              <BrainCircuit class="w-4.5 h-4.5" :stroke-width="1.8" />
            </span>
            <div>
              <h2 class="text-sm font-semibold">AI Provider</h2>
              <p class="text-xs text-muted">Translation · Language detection</p>
            </div>
            <span :class="status.ai.configured ? 'pill-success' : 'pill-warning'" class="ml-auto">
              {{ status.ai.configured ? 'Connected' : 'Stub' }}
            </span>
          </div>
          <dl class="text-sm space-y-1.5">
            <div class="flex justify-between gap-4">
              <dt class="text-muted">Provider</dt>
              <dd class="font-medium">{{ status.ai.provider }}</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="text-muted">Model</dt>
              <dd class="font-medium">{{ status.ai.model || 'n/a' }}</dd>
            </div>
            <div class="flex justify-between gap-4">
              <dt class="text-muted">Environment</dt>
              <dd class="font-medium">{{ status.environment }}</dd>
            </div>
          </dl>
          <p class="text-xs text-muted mt-3 leading-relaxed">
            Set <code class="bg-canvas px-1 rounded">AI_API_KEY</code> (DeepSeek by default, or
            <code class="bg-canvas px-1 rounded">AI_PROVIDER=openai</code>). Without a key Bridge falls back
            to an offline demo phrasebook.
          </p>
        </section>

        <!-- Webhook URLs -->
        <section class="card p-5 lg:col-span-2">
          <div class="flex items-center gap-2.5 mb-3">
            <span class="grid place-items-center w-9 h-9 rounded-md bg-comms-soft text-comms">
              <ShieldCheck class="w-4.5 h-4.5" :stroke-width="1.8" />
            </span>
            <div>
              <h2 class="text-sm font-semibold">Webhook URLs</h2>
              <p class="text-xs text-muted">Register these in the Africa's Talking dashboard</p>
            </div>
          </div>
          <div class="space-y-2">
            <div v-for="(url, key) in webhookUrls" :key="key" class="flex items-center gap-2">
              <span class="text-xs text-muted w-14 shrink-0 capitalize">{{ key }}</span>
              <code class="flex-1 text-xs bg-canvas rounded-md px-2.5 py-2 overflow-x-auto thin-scroll whitespace-nowrap">{{ url }}</code>
              <button class="btn-ghost shrink-0" :title="`Copy ${key} webhook URL`" @click="copy(url, key)">
                <Check v-if="copied === key" class="w-4 h-4 text-success" :stroke-width="1.8" />
                <Copy v-else class="w-4 h-4" :stroke-width="1.8" />
              </button>
            </div>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>
