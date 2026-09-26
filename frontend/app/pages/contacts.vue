<script setup lang="ts">
import { Plus, Trash2, Send, Lock, Sparkles, ArrowLeftRight } from 'lucide-vue-next'
import type { Contact } from '~/types'

definePageMeta({ layout: 'default' })

const api = useApi()
const { languages, load: loadLanguages } = useLanguages()

const contacts = ref<Contact[]>([])
const loading = ref(true)
const error = ref('')
const search = ref('')

const form = reactive({ phone_number: '', name: '', language: '' })
const saving = ref(false)
const formError = ref('')

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return contacts.value
  return contacts.value.filter((c) =>
    `${c.name} ${c.phone_number} ${c.language_name ?? ''}`.toLowerCase().includes(q),
  )
})

async function load() {
  try {
    contacts.value = await api<Contact[]>('/contacts')
    error.value = ''
  } catch {
    error.value = 'Could not load contacts.'
  } finally {
    loading.value = false
  }
}

function detail(err: any, fallback: string) {
  const d = err?.data?.detail
  return Array.isArray(d) ? d.map((x: any) => x.msg).join('; ') : d || fallback
}

async function addContact() {
  if (!form.phone_number.trim()) return
  saving.value = true
  formError.value = ''
  try {
    await api<Contact>('/contacts', {
      method: 'POST',
      body: { phone_number: form.phone_number, name: form.name, language: form.language || null },
    })
    form.phone_number = ''
    form.name = ''
    form.language = ''
    await load()
  } catch (err) {
    formError.value = detail(err, 'Could not save the contact.')
  } finally {
    saving.value = false
  }
}

async function update(contact: Contact, patch: { name?: string; language?: string }) {
  try {
    const updated = await api<Contact>(`/contacts/${contact.id}`, { method: 'PATCH', body: patch })
    Object.assign(contact, updated)
  } catch (err) {
    error.value = detail(err, 'Could not update the contact.')
  }
}

async function remove(contact: Contact) {
  if (!window.confirm(`Delete ${contact.name || contact.phone_number}?`)) return
  try {
    await api(`/contacts/${contact.id}`, { method: 'DELETE' })
    contacts.value = contacts.value.filter((c) => c.id !== contact.id)
  } catch {
    error.value = 'Could not delete the contact.'
  }
}

onMounted(() => Promise.all([load(), loadLanguages()]))
</script>

<template>
  <div>
    <div class="mb-5">
      <h1 class="text-xl font-semibold tracking-tight">Contacts</h1>
      <p class="text-sm text-muted mt-0.5">
        People Bridge talks to and the language each one reads. Languages are learned automatically from their messages — or set them here.
      </p>
    </div>

    <form class="card p-4 mb-5 grid gap-3 sm:grid-cols-[1.2fr_1fr_1fr_auto] items-end" @submit.prevent="addContact">
      <div>
        <label class="label" for="c-phone">Phone number</label>
        <input id="c-phone" v-model="form.phone_number" class="input" placeholder="+254712345678" inputmode="tel" required>
      </div>
      <div>
        <label class="label" for="c-name">Name</label>
        <input id="c-name" v-model="form.name" class="input" placeholder="Optional">
      </div>
      <div>
        <label class="label" for="c-lang">Language</label>
        <select id="c-lang" v-model="form.language" class="input">
          <option value="">Detect automatically</option>
          <option v-for="l in languages" :key="l.code" :value="l.code">{{ l.name }}</option>
        </select>
      </div>
      <button class="btn-primary h-9" :disabled="saving">
        <Plus class="w-4 h-4" /> {{ saving ? 'Saving…' : 'Add contact' }}
      </button>
      <p v-if="formError" class="text-xs text-error sm:col-span-4">{{ formError }}</p>
    </form>

    <p v-if="error" class="card p-4 text-sm text-error bg-error-soft border-error/40 mb-4">{{ error }}</p>

    <div class="card">
      <div class="px-5 py-3 border-b border-line flex items-center gap-3">
        <h2 class="text-sm font-semibold mr-auto whitespace-nowrap">{{ contacts.length }} contact{{ contacts.length === 1 ? '' : 's' }}</h2>
        <div class="w-56"><input v-model="search" class="input h-8 text-xs" placeholder="Search name, number, language"></div>
      </div>

      <div v-if="loading" class="p-5 space-y-3">
        <div v-for="i in 4" :key="i" class="h-12 rounded bg-canvas animate-pulse" />
      </div>

      <div v-else-if="filtered.length" class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="text-xs text-muted text-left">
            <tr class="border-b border-line">
              <th class="font-medium px-5 py-2">Contact</th>
              <th class="font-medium px-3 py-2">Language</th>
              <th class="font-medium px-3 py-2 hidden md:table-cell">Chatting with</th>
              <th class="font-medium px-3 py-2 hidden sm:table-cell text-right">Messages</th>
              <th class="px-5 py-2" />
            </tr>
          </thead>
          <tbody class="divide-y divide-line">
            <tr v-for="c in filtered" :key="c.id" class="hover:bg-canvas/50">
              <td class="px-5 py-2.5">
                <input
                  class="bg-transparent font-medium w-full min-w-[120px] rounded px-1 -mx-1 hover:bg-canvas focus:bg-surface focus:outline-none focus:ring-2 focus:ring-signal/30"
                  :value="c.name"
                  placeholder="Add a name"
                  @change="update(c, { name: ($event.target as HTMLInputElement).value })"
                >
                <p class="text-xs text-muted tabular-nums">{{ c.phone_number }}</p>
              </td>
              <td class="px-3 py-2.5">
                <div class="flex items-center gap-1.5">
                  <select
                    class="input h-8 text-xs w-40"
                    :value="c.language || ''"
                    @change="update(c, { language: ($event.target as HTMLSelectElement).value })"
                  >
                    <option value="">Detect automatically</option>
                    <option v-for="l in languages" :key="l.code" :value="l.code">{{ l.name }}</option>
                  </select>
                  <Lock v-if="c.language_locked" class="w-3.5 h-3.5 text-muted" title="Set explicitly" />
                  <Sparkles v-else-if="c.language" class="w-3.5 h-3.5 text-comms" title="Learned from their messages" />
                </div>
              </td>
              <td class="px-3 py-2.5 hidden md:table-cell text-xs">
                <span v-if="c.partner_number" class="inline-flex items-center gap-1 text-ink">
                  <ArrowLeftRight class="w-3.5 h-3.5 text-signal" /> {{ c.partner_number }}
                </span>
                <span v-else class="text-muted">—</span>
              </td>
              <td class="px-3 py-2.5 hidden sm:table-cell text-right tabular-nums text-muted">{{ c.message_count }}</td>
              <td class="px-5 py-2.5">
                <div class="flex justify-end gap-1">
                  <NuxtLink :to="{ path: '/messages', query: { to: c.phone_number } }" class="btn-ghost h-8 w-8 px-0" title="Send a message">
                    <Send class="w-4 h-4" />
                  </NuxtLink>
                  <button class="btn-ghost h-8 w-8 px-0 hover:text-error" title="Delete" @click="remove(c)">
                    <Trash2 class="w-4 h-4" />
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else class="p-12 text-center">
        <p class="text-sm font-medium">{{ contacts.length ? 'No matches' : 'No contacts yet' }}</p>
        <p v-if="!contacts.length" class="text-sm text-muted mt-1">
          Contacts appear automatically when people text Bridge, or add them above.
        </p>
      </div>
    </div>
  </div>
</template>
