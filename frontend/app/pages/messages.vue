<script setup lang="ts">
import {
  Send, X, Languages, ArrowDownLeft, ArrowUpRight, RefreshCw, Eye, UserPlus,
  CheckCircle2, AlertCircle, ArrowRight, Terminal,
} from 'lucide-vue-next'
import type {
  Contact, MessageLogEntry, MessagingInfo, SendResponse,
} from '~/types'

definePageMeta({ layout: 'default' })

const api = useApi()
const route = useRoute()
const { languages, load: loadLanguages, nameOf } = useLanguages()

// ---------------------------------------------------------------- compose
const recipients = ref<string[]>([])
const recipientDraft = ref('')
const text = ref('')
const languageMode = ref('contact')
const sending = ref(false)
const sendError = ref('')
const lastSend = ref<SendResponse | null>(null)
const contacts = ref<Contact[]>([])
const info = ref<MessagingInfo | null>(null)

const segments = computed(() => smsSegments(text.value))
const contactByPhone = computed(() => new Map(contacts.value.map((c) => [c.phone_number, c])))
const availableContacts = computed(() =>
  contacts.value.filter((c) => !recipients.value.includes(c.phone_number)),
)

function addRecipients(raw: string) {
  for (const part of raw.split(/[,;\n]+/)) {
    const value = part.trim()
    if (value && !recipients.value.includes(value)) recipients.value.push(value)
  }
  recipientDraft.value = ''
}

function onRecipientKey(event: KeyboardEvent) {
  if (['Enter', ',', ';'].includes(event.key)) {
    event.preventDefault()
    addRecipients(recipientDraft.value)
  } else if (event.key === 'Backspace' && !recipientDraft.value && recipients.value.length) {
    recipients.value.pop()
  }
}

function removeRecipient(value: string) {
  recipients.value = recipients.value.filter((r) => r !== value)
}

function recipientLabel(phone: string) {
  const contact = contactByPhone.value.get(phone)
  if (!contact) return phone
  return contact.name || phone
}

function recipientLanguage(phone: string) {
  if (languageMode.value === 'none') return null
  if (languageMode.value !== 'contact') return languageMode.value
  return contactByPhone.value.get(phone)?.language ?? null
}

// ---------------------------------------------------------------- preview
const previews = ref<{ language: string; text: string }[]>([])
const previewing = ref(false)
const previewError = ref('')

const previewLanguages = computed(() => {
  if (languageMode.value === 'none') return []
  if (languageMode.value !== 'contact') return [languageMode.value]
  const codes = recipients.value
    .map((r) => contactByPhone.value.get(r)?.language)
    .filter((code): code is string => !!code)
  return [...new Set(codes)].slice(0, 4)
})

async function preview() {
  previewError.value = ''
  previews.value = []
  if (!text.value.trim() || !previewLanguages.value.length) return
  previewing.value = true
  try {
    previews.value = await Promise.all(
      previewLanguages.value.map(async (language) => {
        const result = await api<{ text: string }>('/messages/translate', {
          method: 'POST',
          body: { text: text.value, language },
        })
        return { language, text: result.text }
      }),
    )
  } catch (err: any) {
    previewError.value = err?.data?.detail || 'Translation preview failed.'
  } finally {
    previewing.value = false
  }
}

watch([text, languageMode], () => { previews.value = [] })

async function send() {
  if (recipientDraft.value.trim()) addRecipients(recipientDraft.value)
  if (!recipients.value.length || !text.value.trim()) return
  sending.value = true
  sendError.value = ''
  lastSend.value = null
  try {
    lastSend.value = await api<SendResponse>('/messages/send', {
      method: 'POST',
      body: { recipients: recipients.value, text: text.value, language: languageMode.value },
    })
    if (!lastSend.value.failed) {
      text.value = ''
      recipients.value = []
    }
    await Promise.all([loadLog(), loadContacts()])
  } catch (err: any) {
    const detail = err?.data?.detail
    sendError.value = Array.isArray(detail) ? detail.map((d: any) => d.msg).join('; ') : detail || 'Sending failed.'
  } finally {
    sending.value = false
  }
}

// -------------------------------------------------------------------- log
const log = ref<MessageLogEntry[]>([])
const logLoading = ref(true)
const logError = ref('')
const filter = ref<'all' | 'inbound' | 'outbound'>('all')
const search = ref('')
const autoRefresh = ref(true)
let timer: ReturnType<typeof setInterval> | undefined

const filteredLog = computed(() => {
  const q = search.value.replace(/\s/g, '')
  return log.value.filter((m) => {
    if (filter.value !== 'all' && m.direction !== filter.value) return false
    if (q && !`${m.from_number}${m.to_number}`.includes(q)) return false
    return true
  })
})

async function loadLog() {
  try {
    log.value = await api<MessageLogEntry[]>('/messages/log', { query: { limit: 200 } })
    logError.value = ''
  } catch {
    logError.value = 'Could not load messages.'
  } finally {
    logLoading.value = false
  }
}

async function loadContacts() {
  try {
    contacts.value = await api<Contact[]>('/contacts')
  } catch {
    contacts.value = []
  }
}

const KIND_LABEL: Record<string, string> = {
  inbound: 'Received',
  relay: 'Relayed',
  broadcast: 'Sent',
  reply: 'Workflow reply',
  system: 'Bridge reply',
  workflow: 'Workflow',
  answer: 'Assistant answer',
}

function whoLabel(phone: string | null) {
  if (!phone) return '—'
  if (info.value?.default_sender && phone === info.value.default_sender) return `Bridge (${phone})`
  const contact = contactByPhone.value.get(phone)
  return contact?.name ? `${contact.name}` : phone
}

function when(value: string) {
  const d = new Date(value)
  const sameDay = d.toDateString() === new Date().toDateString()
  return sameDay
    ? d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

onMounted(async () => {
  const preset = route.query.to
  if (typeof preset === 'string' && preset) addRecipients(preset)
  await Promise.all([
    loadLanguages(),
    loadContacts(),
    loadLog(),
    api<MessagingInfo>('/messages/info').then((r) => (info.value = r)).catch(() => {}),
  ])
  timer = setInterval(() => { if (autoRefresh.value && !document.hidden) loadLog() }, 8000)
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div>
    <div class="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-xl font-semibold tracking-tight">Messages</h1>
        <p class="text-sm text-muted mt-0.5">
          Send SMS that arrive in each person's own language, and follow every message Bridge relays
        </p>
      </div>
      <div v-if="info" class="flex items-center gap-2 text-xs">
        <span :class="info.ai_configured ? 'pill-success' : 'pill-warning'">
          <Languages class="w-3 h-3" /> {{ info.ai_configured ? `AI: ${info.ai_provider}` : 'AI: offline demo' }}
        </span>
        <span class="pill-neutral">From {{ info.default_sender || 'default sender' }}</span>
        <span v-if="info.sandbox" class="pill-warning">Sandbox</span>
      </div>
    </div>

    <div class="grid gap-5 lg:grid-cols-5">
      <!-- Compose -->
      <div class="lg:col-span-2 space-y-5 min-w-0">
        <section class="card p-5">
          <h2 class="text-sm font-semibold mb-4">New message</h2>

          <label class="label" for="recipient-input">To</label>
          <div
            class="min-h-9 w-full rounded-md border border-line bg-surface px-2 py-1 flex flex-wrap gap-1.5 items-center focus-within:ring-2 focus-within:ring-signal/30 focus-within:border-signal"
          >
            <span
              v-for="r in recipients"
              :key="r"
              class="inline-flex items-center gap-1 rounded bg-signal-soft text-signal text-xs font-medium pl-2 pr-1 h-6"
            >
              {{ recipientLabel(r) }}
              <span v-if="recipientLanguage(r)" class="text-signal/70">· {{ recipientLanguage(r) }}</span>
              <button class="hover:bg-signal/10 rounded p-0.5" :aria-label="`Remove ${r}`" @click="removeRecipient(r)">
                <X class="w-3 h-3" />
              </button>
            </span>
            <input
              id="recipient-input"
              v-model="recipientDraft"
              class="flex-1 min-w-[140px] h-7 text-sm bg-transparent outline-none placeholder:text-muted/70"
              placeholder="+254712345678, +2348031234567"
              inputmode="tel"
              @keydown="onRecipientKey"
              @blur="recipientDraft.trim() && addRecipients(recipientDraft)"
            >
          </div>
          <div v-if="availableContacts.length" class="mt-2 flex items-center gap-2">
            <UserPlus class="w-3.5 h-3.5 text-muted shrink-0" />
            <select
              class="input h-8 text-xs"
              :value="''"
              @change="addRecipients(($event.target as HTMLSelectElement).value); ($event.target as HTMLSelectElement).value = ''"
            >
              <option value="" disabled>Add a contact…</option>
              <option v-for="c in availableContacts" :key="c.id" :value="c.phone_number">
                {{ c.name || c.phone_number }}{{ c.language_name ? ` — ${c.language_name}` : '' }}
              </option>
            </select>
          </div>

          <label class="label mt-4" for="message-text">Message</label>
          <textarea
            id="message-text"
            v-model="text"
            rows="5"
            maxlength="1600"
            class="input h-auto py-2 leading-relaxed resize-y"
            placeholder="Write in any language. Bridge translates it for each recipient."
          />
          <div class="mt-1 flex justify-between text-[11px] text-muted tabular-nums">
            <span>{{ segments.unicode ? 'Unicode' : 'GSM-7' }} · {{ segments.parts }} SMS part{{ segments.parts === 1 ? '' : 's' }}</span>
            <span>{{ segments.length }} / {{ segments.limit }}</span>
          </div>

          <label class="label mt-4" for="language-mode">Deliver in</label>
          <select id="language-mode" v-model="languageMode" class="input">
            <option value="contact">Each recipient's language (from contacts)</option>
            <option value="none">Original text — don't translate</option>
            <optgroup label="Everyone in…">
              <option v-for="l in languages" :key="l.code" :value="l.code">{{ l.name }}</option>
            </optgroup>
          </select>
          <p v-if="languageMode === 'contact'" class="text-[11px] text-muted mt-1">
            Recipients without a known language get the original text. Bridge learns languages from the messages people send.
          </p>

          <div v-if="previews.length" class="mt-4 space-y-2">
            <div v-for="p in previews" :key="p.language" class="rounded-md bg-canvas border border-line p-3">
              <p class="text-[11px] font-medium text-muted mb-1">{{ nameOf(p.language) }}</p>
              <p class="text-sm whitespace-pre-wrap">{{ p.text }}</p>
            </div>
          </div>
          <p v-if="previewError" class="text-xs text-error mt-2">{{ previewError }}</p>
          <p v-if="sendError" class="text-xs text-error mt-2">{{ sendError }}</p>

          <div class="mt-4 flex items-center justify-end gap-2">
            <button
              class="btn-secondary"
              :disabled="!text.trim() || !previewLanguages.length || previewing"
              :title="previewLanguages.length ? 'Preview the translation' : 'Add recipients with a known language, or pick a language'"
              @click="preview"
            >
              <Eye class="w-4 h-4" /> {{ previewing ? 'Translating…' : 'Preview' }}
            </button>
            <button class="btn-primary" :disabled="sending || !text.trim() || (!recipients.length && !recipientDraft.trim())" @click="send">
              <Send class="w-4 h-4" /> {{ sending ? 'Sending…' : `Send${recipients.length > 1 ? ` to ${recipients.length}` : ''}` }}
            </button>
          </div>

          <div v-if="lastSend" class="mt-4 border-t border-line pt-4">
            <p class="text-xs font-medium mb-2">
              {{ lastSend.sent }} sent<template v-if="lastSend.failed"> · <span class="text-error">{{ lastSend.failed }} failed</span></template>
            </p>
            <ul class="space-y-2">
              <li v-for="r in lastSend.results" :key="r.to" class="flex gap-2 text-xs">
                <CheckCircle2 v-if="r.status !== 'failed'" class="w-4 h-4 text-success shrink-0" />
                <AlertCircle v-else class="w-4 h-4 text-error shrink-0" />
                <div class="min-w-0">
                  <p class="font-medium">
                    {{ recipientLabel(r.to) }}
                    <span v-if="r.target_language" class="text-muted font-normal">· {{ nameOf(r.target_language) }}</span>
                  </p>
                  <p v-if="r.error" class="text-error">{{ r.error }}</p>
                  <p v-else class="text-muted truncate">{{ r.text }}</p>
                </div>
              </li>
            </ul>
          </div>
        </section>

        <!-- How people use Bridge by SMS -->
        <section class="card p-5">
          <div class="flex items-center gap-2 mb-3">
            <Terminal class="w-4 h-4 text-signal" />
            <h2 class="text-sm font-semibold">Chat by SMS through Bridge</h2>
          </div>
          <p class="text-xs text-muted mb-3">
            Anyone can text {{ info?.default_sender || 'the Bridge shortcode' }} — no app, no data. Each person reads the conversation in their own language.
          </p>
          <dl class="space-y-2 text-xs">
            <div class="flex gap-3"><dt class="font-mono font-medium w-40 shrink-0">TO +2547… Hello</dt><dd class="text-muted">Start a chat with someone</dd></div>
            <div class="flex gap-3"><dt class="font-mono font-medium w-40 shrink-0">(any text)</dt><dd class="text-muted">Reply in the current chat</dd></div>
            <div class="flex gap-3"><dt class="font-mono font-medium w-40 shrink-0">LANG Swahili</dt><dd class="text-muted">Choose your language</dd></div>
            <div class="flex gap-3"><dt class="font-mono font-medium w-40 shrink-0">STOP</dt><dd class="text-muted">End the chat</dd></div>
            <div class="flex gap-3"><dt class="font-mono font-medium w-40 shrink-0">HELP</dt><dd class="text-muted">Show these commands</dd></div>
            <div class="flex gap-3"><dt class="font-mono font-medium w-40 shrink-0">(a question)</dt><dd class="text-muted">Answered from your <NuxtLink to="/knowledge" class="text-signal hover:underline">knowledge base</NuxtLink> when not in a chat</dd></div>
            <div class="flex gap-3"><dt class="font-mono font-medium w-40 shrink-0">ASK …</dt><dd class="text-muted">Ask a question during a chat</dd></div>
          </dl>
        </section>
      </div>

      <!-- Log -->
      <section class="lg:col-span-3 card flex flex-col min-h-[420px] min-w-0">
        <div class="px-5 py-3 border-b border-line flex flex-wrap items-center gap-2">
          <h2 class="text-sm font-semibold mr-auto">Message log</h2>
          <div class="inline-flex rounded-md border border-line p-0.5 text-xs">
            <button
              v-for="option in (['all', 'inbound', 'outbound'] as const)"
              :key="option"
              class="px-2.5 h-7 rounded capitalize"
              :class="filter === option ? 'bg-canvas font-medium text-ink' : 'text-muted hover:text-ink'"
              @click="filter = option"
            >
              {{ option }}
            </button>
          </div>
          <div class="w-36"><input v-model="search" class="input h-8 text-xs" placeholder="Filter by number" inputmode="tel"></div>
          <button class="btn-ghost h-8 w-8 px-0" title="Refresh" @click="loadLog">
            <RefreshCw class="w-4 h-4" />
          </button>
          <label class="flex items-center gap-1 text-xs text-muted cursor-pointer select-none">
            <input v-model="autoRefresh" type="checkbox" class="accent-signal"> Live
          </label>
        </div>

        <p v-if="logError" class="m-4 text-sm text-error">{{ logError }}</p>
        <div v-if="logLoading" class="p-5 space-y-3">
          <div v-for="i in 5" :key="i" class="h-14 rounded bg-canvas animate-pulse" />
        </div>

        <ul v-else-if="filteredLog.length" class="divide-y divide-line overflow-y-auto max-h-[70vh] thin-scroll">
          <li v-for="m in filteredLog" :key="m.id" class="px-5 py-3 flex gap-3">
            <span
              class="grid place-items-center w-8 h-8 rounded-md shrink-0 mt-0.5"
              :class="m.direction === 'inbound' ? 'bg-comms-soft text-comms' : 'bg-signal-soft text-signal'"
            >
              <ArrowDownLeft v-if="m.direction === 'inbound'" class="w-4 h-4" />
              <ArrowUpRight v-else class="w-4 h-4" />
            </span>
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs">
                <span class="font-medium text-ink">{{ whoLabel(m.from_number) }}</span>
                <ArrowRight class="w-3 h-3 text-muted" />
                <span class="font-medium text-ink">{{ whoLabel(m.to_number) }}</span>
                <span class="pill-neutral ml-1">{{ KIND_LABEL[m.kind] || m.kind }}</span>
                <span v-if="m.target_language" class="pill bg-signal-soft text-signal">
                  <Languages class="w-3 h-3" />
                  {{ m.source_language && m.source_language !== m.target_language ? `${m.source_language} → ` : '' }}{{ m.target_language }}
                </span>
                <span v-if="m.status === 'failed'" class="pill-error">failed</span>
                <span class="ml-auto text-muted tabular-nums">{{ when(m.created_at) }}</span>
              </div>
              <p class="text-sm mt-1 whitespace-pre-wrap break-words">{{ m.text }}</p>
              <p v-if="m.original_text && m.original_text !== m.text" class="text-xs text-muted mt-1 whitespace-pre-wrap break-words">
                <span class="font-medium">Original:</span> {{ m.original_text }}
              </p>
              <p v-if="m.error" class="text-xs text-error mt-1">{{ m.error }}</p>
            </div>
          </li>
        </ul>

        <div v-else class="flex-1 grid place-items-center p-12 text-center">
          <div>
            <p class="text-sm font-medium">No messages yet</p>
            <p class="text-sm text-muted mt-1 max-w-sm">
              Send one from here, or text <span class="font-mono">HELP</span> to
              {{ info?.default_sender || 'your shortcode' }} from the Africa's Talking simulator.
            </p>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
