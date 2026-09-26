<script setup lang="ts">
import {
  Globe, FileText, Sheet, Database, NotebookPen, Plus, RefreshCw, Trash2, ChevronDown,
  Loader2, CheckCircle2, AlertTriangle, MessageCircleQuestion, ShieldCheck, Quote, X,
  Code2, Copy, Check, KeyRound,
} from 'lucide-vue-next'
import type {
  ApiKey, ApiKeyCreated, AskResult, BusinessProfile, KnowledgeChunk, KnowledgeKind, KnowledgeQuery, KnowledgeSource,
} from '~/types'

definePageMeta({ layout: 'default' })

const api = useApi()

const KINDS: { kind: KnowledgeKind; label: string; icon: any; hint: string }[] = [
  { kind: 'website', label: 'Website', icon: Globe, hint: 'Bridge reads your site and the pages it links to.' },
  { kind: 'google_doc', label: 'Google Doc', icon: FileText, hint: "Share the doc as 'Anyone with the link can view'." },
  { kind: 'google_sheet', label: 'Google Sheet', icon: Sheet, hint: "Price lists, stock, branches… Share as 'Anyone with the link can view'. Include ?gid= for a specific tab." },
  { kind: 'database', label: 'Database', icon: Database, hint: 'PostgreSQL or MySQL. Bridge runs your SELECT in a read-only session; the connection string is encrypted and never shown again.' },
  { kind: 'text', label: 'Text / FAQ', icon: NotebookPen, hint: 'Paste FAQs, policies, opening hours, prices: anything customers ask about.' },
]
const kindMeta = (kind: string) => KINDS.find((k) => k.kind === kind) ?? KINDS[4]!

// ------------------------------------------------------------------ data
const profile = ref<BusinessProfile | null>(null)
const sources = ref<KnowledgeSource[]>([])
const queries = ref<KnowledgeQuery[]>([])
const loading = ref(true)
const error = ref('')
let poll: ReturnType<typeof setInterval> | undefined

async function loadProfile(syncForm = false) {
  profile.value = await api<BusinessProfile>('/knowledge/profile')
  if (!syncForm) return
  Object.assign(profileForm, {
    name: profile.value.name, description: profile.value.description, contact: profile.value.contact,
    fallback_message: profile.value.fallback_message, assistant_enabled: profile.value.assistant_enabled,
  })
}
async function loadSources() {
  sources.value = await api<KnowledgeSource[]>('/knowledge/sources')
}
const unansweredOnly = ref(false)
async function loadQueries() {
  queries.value = await api<KnowledgeQuery[]>('/knowledge/queries', { query: { unanswered: unansweredOnly.value, limit: 30 } })
}
watch(unansweredOnly, loadQueries)

async function refreshAll() {
  try {
    await Promise.all([loadProfile(true), loadSources(), loadQueries()])
    error.value = ''
  } catch {
    error.value = 'Could not load the knowledge base.'
  } finally {
    loading.value = false
  }
}

const anySyncing = computed(() => sources.value.some((s) => s.status === 'syncing' || s.status === 'pending'))
watch(anySyncing, (syncing) => {
  clearInterval(poll)
  if (syncing) {
    poll = setInterval(async () => {
      await loadSources().catch(() => {})
      if (!anySyncing.value) loadProfile().catch(() => {})
    }, 3000)
  }
})

onMounted(refreshAll)
onUnmounted(() => clearInterval(poll))

// --------------------------------------------------------------- profile
const profileForm = reactive({ name: '', description: '', contact: '', fallback_message: '', assistant_enabled: true })
const savingProfile = ref(false)
const profileSaved = ref(false)
async function saveProfile() {
  savingProfile.value = true
  profileSaved.value = false
  try {
    profile.value = await api<BusinessProfile>('/knowledge/profile', { method: 'PUT', body: profileForm })
    profileSaved.value = true
    setTimeout(() => (profileSaved.value = false), 2500)
  } catch {
    error.value = 'Could not save the business profile.'
  } finally {
    savingProfile.value = false
  }
}

// ---------------------------------------------------------------- sources
const adding = ref(false)
const newKind = ref<KnowledgeKind>('website')
const newSource = reactive({ name: '', url: '', max_pages: 10, query: '', secret: '', text: '' })
const addError = ref('')
const submitting = ref(false)

function resetNewSource() {
  Object.assign(newSource, { name: '', url: '', max_pages: 10, query: '', secret: '', text: '' })
  addError.value = ''
}

async function addSource() {
  submitting.value = true
  addError.value = ''
  const config: Record<string, unknown> =
    newKind.value === 'website' ? { url: newSource.url, max_pages: newSource.max_pages }
      : newKind.value === 'database' ? { query: newSource.query }
        : newKind.value === 'text' ? { text: newSource.text }
          : { url: newSource.url }
  try {
    const created = await api<KnowledgeSource>('/knowledge/sources', {
      method: 'POST',
      body: { kind: newKind.value, name: newSource.name, config, secret: newKind.value === 'database' ? newSource.secret : null },
    })
    sources.value = [created, ...sources.value]
    resetNewSource()
    adding.value = false
  } catch (err: any) {
    addError.value = err?.data?.detail || 'Could not add the source.'
  } finally {
    submitting.value = false
  }
}

async function syncSource(source: KnowledgeSource) {
  const updated = await api<KnowledgeSource>(`/knowledge/sources/${source.id}/sync`, { method: 'POST' })
  Object.assign(source, updated)
}

async function removeSource(source: KnowledgeSource) {
  if (!window.confirm(`Remove "${source.name}" and everything Bridge learned from it?`)) return
  await api(`/knowledge/sources/${source.id}`, { method: 'DELETE' })
  sources.value = sources.value.filter((s) => s.id !== source.id)
  loadProfile().catch(() => {})
}

const expanded = ref<number | null>(null)
const passages = ref<KnowledgeChunk[]>([])
async function togglePassages(source: KnowledgeSource) {
  if (expanded.value === source.id) {
    expanded.value = null
    return
  }
  expanded.value = source.id
  passages.value = []
  passages.value = await api<KnowledgeChunk[]>(`/knowledge/sources/${source.id}/chunks`)
}

function sourceDetail(source: KnowledgeSource) {
  if (source.kind === 'database') return `${source.config.dialect === 'mysql' ? 'MySQL' : 'PostgreSQL'} · ${source.config.query}`
  if (source.kind === 'text') return `${(source.config.text || '').slice(0, 90)}…`
  return source.config.url
}

// -------------------------------------------------------------------- ask
const question = ref('')
const asking = ref(false)
const answer = ref<AskResult | null>(null)
const askError = ref('')
async function ask() {
  if (!question.value.trim()) return
  asking.value = true
  askError.value = ''
  answer.value = null
  try {
    answer.value = await api<AskResult>('/knowledge/ask', { method: 'POST', body: { question: question.value } })
    loadQueries().catch(() => {})
    loadProfile().catch(() => {})
  } catch (err: any) {
    askError.value = err?.data?.detail || 'The assistant could not answer.'
  } finally {
    asking.value = false
  }
}

const REASONS: Record<string, string> = {
  answered: 'Answered from your sources',
  not_in_sources: 'Not in your sources, fallback sent',
  unverified: 'Answer could not be verified against your sources, fallback sent',
  no_match: 'Nothing relevant found, fallback sent',
  no_knowledge: 'No ready sources yet, fallback sent',
  ai_unavailable: 'AI provider unavailable, fallback sent',
  not_a_question: 'Greeting, welcome message sent',
  disabled: 'Assistant is switched off',
}

function when(value: string | null) {
  if (!value) return 'never'
  return new Date(value).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// ------------------------------------------------------------- API keys
const config = useRuntimeConfig()
const publicAskUrl = computed(() => {
  const apiBase = (config.public.apiBase as string) || ''
  const base = apiBase.startsWith('http') ? apiBase : `${window?.location?.origin || ''}/api/v1`
  return `${base}/public/assistant/ask`
})

const apiKeys = ref<ApiKey[]>([])
const keysLoading = ref(true)
const keysError = ref('')
const newKeyName = ref('')
const creatingKey = ref(false)
// Shown once, right after creation; never fetched again.
const justCreatedKey = ref<ApiKeyCreated | null>(null)
const copied = ref(false)

async function loadApiKeys() {
  try {
    apiKeys.value = await api<ApiKey[]>('/api-keys')
    keysError.value = ''
  } catch {
    keysError.value = 'Could not load API keys.'
  } finally {
    keysLoading.value = false
  }
}
onMounted(loadApiKeys)

async function createApiKey() {
  creatingKey.value = true
  justCreatedKey.value = null
  try {
    const created = await api<ApiKeyCreated>('/api-keys', { method: 'POST', body: { name: newKeyName.value.trim() } })
    justCreatedKey.value = created
    apiKeys.value = [created, ...apiKeys.value]
    newKeyName.value = ''
  } catch {
    keysError.value = 'Could not create the key.'
  } finally {
    creatingKey.value = false
  }
}

async function revokeApiKey(key: ApiKey) {
  if (!window.confirm(`Revoke "${key.name || key.prefix}"? Anything using it will stop working immediately.`)) return
  const updated = await api<ApiKey>(`/api-keys/${key.id}`, { method: 'DELETE' })
  Object.assign(key, updated)
  if (justCreatedKey.value?.id === key.id) justCreatedKey.value = null
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    setTimeout(() => (copied.value = false), 2000)
  } catch {
    // Clipboard API unavailable; the key/snippet stays selectable in the UI.
  }
}

function snippet(key: string) {
  return `<script>
async function askBridge(question) {
  const res = await fetch('${publicAskUrl.value}', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Api-Key': '${key}' },
    body: JSON.stringify({ question }),
  })
  return res.json() // { answered, answer, language }
}
<\/script>`
}
</script>

<template>
  <div>
    <div class="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-xl font-semibold tracking-tight">Knowledge</h1>
        <p class="text-sm text-muted mt-0.5 max-w-2xl">
          Connect your business information. When customers text a question, Bridge answers in their language using only these sources, and says it doesn't know rather than guessing.
        </p>
      </div>
      <span v-if="profile" :class="profile.available ? 'pill-success' : 'pill-warning'">
        <ShieldCheck class="w-3.5 h-3.5" />
        {{ profile.available ? 'Assistant live on SMS'
          : !profile.ai_configured ? 'Needs an AI key'
            : !profile.assistant_enabled ? 'Assistant switched off' : 'Add a source to go live' }}
      </span>
    </div>

    <p v-if="error" class="card p-4 text-sm text-error bg-error-soft border-error/40 mb-4">{{ error }}</p>

    <div v-if="profile" class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
      <div class="card p-4"><p class="text-xs text-muted">Sources ready</p><p class="text-xl font-semibold tabular-nums mt-1">{{ profile.ready_sources }}<span class="text-sm text-muted font-normal"> / {{ profile.sources }}</span></p></div>
      <div class="card p-4"><p class="text-xs text-muted">Passages</p><p class="text-xl font-semibold tabular-nums mt-1">{{ profile.passages }}</p></div>
      <div class="card p-4"><p class="text-xs text-muted">Questions</p><p class="text-xl font-semibold tabular-nums mt-1">{{ profile.questions }}</p></div>
      <div class="card p-4"><p class="text-xs text-muted">Unanswered</p><p class="text-xl font-semibold tabular-nums mt-1" :class="profile.unanswered ? 'text-warning' : ''">{{ profile.unanswered }}</p></div>
    </div>

    <div class="grid gap-5 lg:grid-cols-3">
      <div class="lg:col-span-2 space-y-5 min-w-0">
        <!-- Sources -->
        <section class="card">
          <div class="px-5 py-3 border-b border-line flex items-center gap-2">
            <h2 class="text-sm font-semibold mr-auto">Sources</h2>
            <button v-if="!adding" class="btn-primary" @click="adding = true">
              <Plus class="w-4 h-4" /> Add source
            </button>
          </div>

          <!-- Add source -->
          <div v-if="adding" class="p-5 border-b border-line bg-canvas/50">
            <div class="flex items-center justify-between mb-3">
              <h3 class="text-sm font-semibold">Add a source</h3>
              <button class="btn-ghost h-8 w-8 px-0" aria-label="Close" @click="adding = false; resetNewSource()">
                <X class="w-4 h-4" />
              </button>
            </div>
            <div class="flex flex-wrap gap-1.5 mb-4">
              <button
                v-for="k in KINDS" :key="k.kind" type="button"
                class="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border text-xs font-medium transition-colors"
                :class="newKind === k.kind ? 'border-signal bg-signal-soft text-signal' : 'border-line bg-surface text-muted hover:text-ink'"
                @click="newKind = k.kind; addError = ''"
              >
                <component :is="k.icon" class="w-3.5 h-3.5" /> {{ k.label }}
              </button>
            </div>
            <p class="text-xs text-muted mb-3">{{ kindMeta(newKind).hint }}</p>

            <form class="grid gap-3 sm:grid-cols-2" @submit.prevent="addSource">
              <div class="sm:col-span-2">
                <label class="label" for="src-name">Name</label>
                <input id="src-name" v-model="newSource.name" class="input" :placeholder="`e.g. ${newKind === 'database' ? 'Product catalogue' : newKind === 'text' ? 'Store FAQ' : 'Company website'}`">
              </div>
              <template v-if="newKind === 'website' || newKind === 'google_doc' || newKind === 'google_sheet'">
                <div :class="newKind === 'website' ? '' : 'sm:col-span-2'">
                  <label class="label" for="src-url">{{ newKind === 'website' ? 'Website address' : 'Share link' }}</label>
                  <input id="src-url" v-model="newSource.url" class="input" required inputmode="url"
                         :placeholder="newKind === 'website' ? 'https://yourbusiness.com' : `https://docs.google.com/${newKind === 'google_doc' ? 'document' : 'spreadsheets'}/d/…`">
                </div>
                <div v-if="newKind === 'website'">
                  <label class="label" for="src-pages">Pages to read (max 30)</label>
                  <input id="src-pages" v-model.number="newSource.max_pages" type="number" min="1" max="30" class="input">
                </div>
              </template>
              <template v-else-if="newKind === 'database'">
                <div class="sm:col-span-2">
                  <label class="label" for="src-dsn">Connection string</label>
                  <input id="src-dsn" v-model="newSource.secret" type="password" class="input font-mono" required autocomplete="off"
                         placeholder="postgresql://readonly_user:password@host:5432/shop">
                  <p class="text-[11px] text-muted mt-1">Use a read-only database user. Stored encrypted; never displayed again.</p>
                </div>
                <div class="sm:col-span-2">
                  <label class="label" for="src-query">SELECT query</label>
                  <textarea id="src-query" v-model="newSource.query" rows="3" class="input h-auto py-2 font-mono text-xs" required
                            placeholder="SELECT name, price, in_stock FROM products WHERE active = true" />
                  <p class="text-[11px] text-muted mt-1">Each row becomes facts like “name: Mangoes; price: 50”. Up to 2,000 rows.</p>
                </div>
              </template>
              <div v-else class="sm:col-span-2">
                <label class="label" for="src-text">Text</label>
                <textarea id="src-text" v-model="newSource.text" rows="8" class="input h-auto py-2 leading-relaxed" required
                          placeholder="Opening hours: Mon–Sat 8am–7pm&#10;Delivery: KES 150 within Nairobi, free above KES 2,000&#10;Payment: M-Pesa Till 552211, cash, Visa" />
              </div>
              <p v-if="addError" class="text-xs text-error sm:col-span-2">{{ addError }}</p>
              <div class="sm:col-span-2 flex justify-end gap-2">
                <button type="button" class="btn-secondary" @click="adding = false; resetNewSource()">Cancel</button>
                <button class="btn-primary" :disabled="submitting">{{ submitting ? 'Adding…' : 'Add and import' }}</button>
              </div>
            </form>
          </div>

          <div v-if="loading" class="p-5 space-y-3">
            <div v-for="i in 3" :key="i" class="h-14 rounded bg-canvas animate-pulse" />
          </div>
          <ul v-else-if="sources.length" class="divide-y divide-line">
            <li v-for="s in sources" :key="s.id" class="px-5 py-3">
              <div class="flex flex-wrap sm:flex-nowrap items-start gap-3">
                <span class="grid place-items-center w-9 h-9 rounded-md bg-signal-soft text-signal shrink-0">
                  <component :is="kindMeta(s.kind).icon" class="w-4 h-4" />
                </span>
                <div class="min-w-0 flex-1">
                  <div class="flex flex-wrap items-center gap-2">
                    <p class="text-sm font-medium">{{ s.name }}</p>
                    <span v-if="s.status === 'ready'" class="pill-success"><CheckCircle2 class="w-3 h-3" /> {{ s.chunk_count }} passage{{ s.chunk_count === 1 ? '' : 's' }}</span>
                    <span v-else-if="s.status === 'error'" class="pill-error"><AlertTriangle class="w-3 h-3" /> Import failed</span>
                    <span v-else class="pill-warning"><Loader2 class="w-3 h-3 animate-spin" /> Importing…</span>
                  </div>
                  <p class="text-xs text-muted truncate mt-0.5">{{ kindMeta(s.kind).label }} · {{ sourceDetail(s) }}</p>
                  <p v-if="s.error" class="text-xs text-error mt-1">{{ s.error }}</p>
                  <p class="text-[11px] text-muted mt-0.5">Last imported {{ when(s.last_synced_at) }}</p>
                </div>
                <div class="flex items-center gap-1 shrink-0 ml-12 sm:ml-0">
                  <button v-if="s.status === 'ready'" class="btn-ghost h-8 px-2 text-xs" @click="togglePassages(s)">
                    Passages <ChevronDown class="w-3.5 h-3.5 transition-transform" :class="expanded === s.id ? 'rotate-180' : ''" />
                  </button>
                  <button class="btn-ghost h-8 w-8 px-0" title="Import again" :disabled="s.status === 'syncing'" @click="syncSource(s)">
                    <RefreshCw class="w-4 h-4" :class="s.status === 'syncing' ? 'animate-spin' : ''" />
                  </button>
                  <button class="btn-ghost h-8 w-8 px-0 hover:text-error" title="Remove" @click="removeSource(s)">
                    <Trash2 class="w-4 h-4" />
                  </button>
                </div>
              </div>
              <div v-if="expanded === s.id" class="mt-3 sm:ml-12 space-y-2 max-h-80 overflow-y-auto thin-scroll">
                <p v-if="!passages.length" class="text-xs text-muted">Loading…</p>
                <div v-for="p in passages" :key="p.id" class="rounded-md border border-line bg-canvas/60 p-3">
                  <p class="text-[11px] text-muted truncate">{{ p.title }} · {{ p.location }}</p>
                  <p class="text-xs mt-1 whitespace-pre-wrap line-clamp-6">{{ p.content }}</p>
                </div>
              </div>
            </li>
          </ul>
          <div v-else class="p-10 text-center">
            <p class="text-sm font-medium">No sources yet</p>
            <p class="text-sm text-muted mt-1">Add your website, a Google Doc or Sheet, a database, or paste your FAQ.</p>
          </div>
        </section>

        <!-- Questions -->
        <section class="card">
          <div class="px-5 py-3 border-b border-line flex items-center gap-2">
            <h2 class="text-sm font-semibold mr-auto">Questions customers asked</h2>
            <label class="flex items-center gap-1.5 text-xs text-muted cursor-pointer select-none">
              <input v-model="unansweredOnly" type="checkbox" class="accent-signal"> Unanswered only
            </label>
          </div>
          <ul v-if="queries.length" class="divide-y divide-line max-h-[480px] overflow-y-auto thin-scroll">
            <li v-for="q in queries" :key="q.id" class="px-5 py-3">
              <div class="flex flex-wrap items-center gap-2 text-xs">
                <span :class="q.answered ? 'pill-success' : q.reason === 'not_a_question' ? 'pill-neutral' : 'pill-warning'">
                  {{ q.answered ? 'Answered' : q.reason === 'not_a_question' ? 'Greeting' : 'Not answered' }}
                </span>
                <span class="text-muted">{{ q.phone_number || (q.channel === 'dashboard' ? 'Test console' : q.channel) }}</span>
                <span v-if="q.language" class="pill-neutral">{{ q.language }}</span>
                <span class="ml-auto text-muted tabular-nums">{{ when(q.created_at) }}</span>
              </div>
              <p class="text-sm font-medium mt-1.5">{{ q.question }}</p>
              <p class="text-xs text-muted mt-0.5 whitespace-pre-wrap">{{ q.answer }}</p>
            </li>
          </ul>
          <p v-else class="p-8 text-center text-sm text-muted">
            {{ unansweredOnly ? 'Every question so far was answered.' : 'No questions yet. Try the test console, or text a question to your shortcode.' }}
          </p>
        </section>
      </div>

      <div class="space-y-5 min-w-0">
        <!-- Test console -->
        <section class="card p-5">
          <div class="flex items-center gap-2 mb-3">
            <MessageCircleQuestion class="w-4 h-4 text-signal" />
            <h2 class="text-sm font-semibold">Test the assistant</h2>
          </div>
          <form @submit.prevent="ask">
            <textarea v-model="question" rows="3" class="input h-auto py-2" placeholder="Ask like a customer would, in any language" />
            <button class="btn-primary w-full mt-2" :disabled="asking || !question.trim()">
              <Loader2 v-if="asking" class="w-4 h-4 animate-spin" /> {{ asking ? 'Thinking…' : 'Ask' }}
            </button>
          </form>
          <p v-if="askError" class="text-xs text-error mt-2">{{ askError }}</p>
          <div v-if="answer" class="mt-4 space-y-3">
            <span :class="answer.answered ? 'pill-success' : 'pill-warning'">{{ REASONS[answer.reason] || answer.reason }}</span>
            <div class="rounded-lg bg-signal-soft/60 border border-signal/20 p-3">
              <p class="text-[11px] text-muted mb-1">SMS reply</p>
              <p class="text-sm whitespace-pre-wrap">{{ answer.answer }}</p>
            </div>
            <div v-if="answer.evidence.length">
              <p class="text-[11px] font-medium text-muted mb-1">Verified against</p>
              <p v-for="(e, i) in answer.evidence" :key="i" class="text-xs flex gap-1.5 mb-1">
                <Quote class="w-3 h-3 text-muted shrink-0 mt-0.5" /> <span>{{ e }}</span>
              </p>
            </div>
            <div v-if="answer.sources.length">
              <p class="text-[11px] font-medium text-muted mb-1">Sources</p>
              <p v-for="s in answer.sources" :key="`${s.source_id}-${s.location}`" class="text-xs text-muted truncate">
                {{ s.source_name }} · {{ s.location }}
              </p>
            </div>
          </div>
          <p class="text-[11px] text-muted mt-4 leading-relaxed">
            Every answer must quote your sources word for word, and every number in it must appear in them. Anything that fails that check is replaced by your fallback message.
          </p>
        </section>

        <!-- Business profile -->
        <section class="card p-5">
          <h2 class="text-sm font-semibold mb-3">Business profile</h2>
          <form class="space-y-3" @submit.prevent="saveProfile">
            <div>
              <label class="label" for="bp-name">Business name</label>
              <input id="bp-name" v-model="profileForm.name" class="input" placeholder="Mama Mboga Grocers">
            </div>
            <div>
              <label class="label" for="bp-desc">What you do</label>
              <textarea id="bp-desc" v-model="profileForm.description" rows="3" class="input h-auto py-2" placeholder="Fresh fruit and vegetables delivered across Nairobi." />
            </div>
            <div>
              <label class="label" for="bp-contact">Contact for customers</label>
              <input id="bp-contact" v-model="profileForm.contact" class="input" placeholder="+254 700 111 222 or hello@shop.co.ke">
            </div>
            <div>
              <label class="label" for="bp-fallback">When the answer isn't in your sources</label>
              <textarea id="bp-fallback" v-model="profileForm.fallback_message" rows="2" maxlength="480" class="input h-auto py-2"
                        placeholder="Sorry, I don't have that information right now." />
              <p class="text-[11px] text-muted mt-1">Your contact is added automatically. Sent in the customer's language.</p>
            </div>
            <label class="flex items-center gap-2 text-sm cursor-pointer select-none">
              <input v-model="profileForm.assistant_enabled" type="checkbox" class="accent-signal w-4 h-4">
              Answer customer questions by SMS
            </label>
            <div class="flex items-center justify-end gap-2">
              <span v-if="profileSaved" class="text-xs text-success">Saved</span>
              <button class="btn-primary" :disabled="savingProfile">{{ savingProfile ? 'Saving…' : 'Save profile' }}</button>
            </div>
          </form>
        </section>

        <!-- API keys: connect a website chatbot or other integration -->
        <section class="card p-5">
          <div class="flex items-center gap-2 mb-1">
            <Code2 class="w-4 h-4 text-signal" />
            <h2 class="text-sm font-semibold">Connect your website chatbot</h2>
          </div>
          <p class="text-xs text-muted mb-3 leading-relaxed">
            Generate a key so your own website, app, or another chatbot can ask this same assistant a question over a plain HTTP endpoint, independent of this dashboard login.
          </p>

          <p v-if="keysError" class="text-xs text-error mb-2">{{ keysError }}</p>

          <form class="flex gap-2 mb-3" @submit.prevent="createApiKey">
            <input v-model="newKeyName" class="input" placeholder="e.g. Marketing site widget" maxlength="255">
            <button class="btn-primary shrink-0" :disabled="creatingKey">
              <Plus class="w-4 h-4" /> {{ creatingKey ? 'Creating…' : 'New key' }}
            </button>
          </form>

          <div v-if="justCreatedKey" class="rounded-lg border border-signal/30 bg-signal-soft/60 p-3 mb-3">
            <p class="text-xs font-medium mb-1.5">Copy this key now, it won't be shown again</p>
            <div class="flex items-center gap-2">
              <code class="text-xs bg-surface border border-line rounded px-2 py-1.5 flex-1 overflow-x-auto whitespace-nowrap">{{ justCreatedKey.key }}</code>
              <button type="button" class="btn-ghost h-8 w-8 px-0 shrink-0" title="Copy key" @click="copyText(justCreatedKey.key)">
                <Check v-if="copied" class="w-4 h-4 text-success" /> <Copy v-else class="w-4 h-4" />
              </button>
            </div>
            <details class="mt-2">
              <summary class="text-xs text-signal cursor-pointer select-none">Show embed snippet</summary>
              <pre class="text-[11px] mt-2 bg-surface border border-line rounded p-2 overflow-x-auto whitespace-pre-wrap">{{ snippet(justCreatedKey.key) }}</pre>
              <p class="text-[11px] text-muted mt-1">POST <code>{{ publicAskUrl }}</code> with header <code>X-Api-Key</code>. Callable from any origin; rate-limited to 30 requests/minute per key.</p>
            </details>
          </div>

          <div v-if="keysLoading" class="h-10 rounded bg-canvas animate-pulse" />
          <ul v-else-if="apiKeys.length" class="divide-y divide-line -mx-5">
            <li v-for="k in apiKeys" :key="k.id" class="px-5 py-2.5 flex items-center gap-2">
              <span class="grid place-items-center w-7 h-7 rounded-md bg-signal-soft text-signal shrink-0">
                <KeyRound class="w-3.5 h-3.5" />
              </span>
              <div class="min-w-0 flex-1">
                <p class="text-xs font-medium truncate">{{ k.name || 'Unnamed key' }}</p>
                <p class="text-[11px] text-muted font-mono">{{ k.prefix }}… · {{ k.request_count }} request{{ k.request_count === 1 ? '' : 's' }} · last used {{ when(k.last_used_at) }}</p>
              </div>
              <span v-if="k.revoked_at" class="pill-neutral">Revoked</span>
              <button v-else class="btn-ghost h-8 w-8 px-0 hover:text-error" title="Revoke" @click="revokeApiKey(k)">
                <Trash2 class="w-4 h-4" />
              </button>
            </li>
          </ul>
          <p v-else class="text-xs text-muted">No keys yet. Create one to get an endpoint and key for your site.</p>
        </section>
      </div>
    </div>
  </div>
</template>
