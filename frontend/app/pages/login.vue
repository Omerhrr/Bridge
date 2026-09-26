<script setup lang="ts">
import { LogIn, ShieldCheck } from 'lucide-vue-next'
import type { SetupStatus } from '~/composables/useAuth'

definePageMeta({ layout: false })

const api = useApi()
const route = useRoute()
const { token, login, register, fetchUser } = useAuth()

const setup = ref<SetupStatus | null>(null)
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const form = reactive({ email: '', password: '', full_name: '', setup_code: '' })

const next = computed(() => {
  const value = route.query.next
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') ? value : '/'
})
const creatingOwner = computed(() => !!setup.value?.needs_setup)

onMounted(async () => {
  // Already signed in? Go straight through.
  if (token.value && await fetchUser()) return navigateTo(next.value)
  try {
    setup.value = await api<SetupStatus>('/auth/setup')
  } catch {
    error.value = 'Bridge is starting up. This can take up to a minute. Refresh in a moment.'
  } finally {
    loading.value = false
  }
})

function message(err: any, fallback: string) {
  const detail = err?.data?.detail
  if (Array.isArray(detail)) return detail.map((d: any) => d.msg).join('; ')
  return detail || fallback
}

async function submit() {
  busy.value = true
  error.value = ''
  try {
    if (creatingOwner.value) {
      await register({
        email: form.email,
        password: form.password,
        full_name: form.full_name,
        setup_code: form.setup_code || undefined,
      })
    } else {
      await login(form.email, form.password)
    }
    await navigateTo(next.value)
  } catch (err) {
    error.value = message(err, creatingOwner.value ? 'Could not create the account.' : 'Sign-in failed.')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="min-h-dvh bg-canvas grid place-items-center px-4 py-10">
    <div class="w-full max-w-sm">
      <div class="flex items-center justify-center gap-2 mb-6">
        <span class="grid place-items-center w-9 h-9 rounded-lg bg-navy">
          <span class="block w-3 h-3 rounded-full bg-comms" />
        </span>
        <span class="text-2xl font-semibold tracking-tight">Bridge</span>
      </div>

      <div class="card p-6">
        <div v-if="loading" class="space-y-3">
          <div class="h-5 w-2/3 rounded bg-canvas animate-pulse" />
          <div class="h-9 rounded bg-canvas animate-pulse" />
          <div class="h-9 rounded bg-canvas animate-pulse" />
        </div>

        <form v-else class="space-y-4" @submit.prevent="submit">
          <div>
            <h1 class="text-base font-semibold flex items-center gap-2">
              <ShieldCheck v-if="creatingOwner" class="w-4 h-4 text-signal" />
              {{ creatingOwner ? 'Create the owner account' : 'Sign in' }}
            </h1>
            <p class="text-xs text-muted mt-1">
              {{ creatingOwner
                ? 'This is the first sign-in. The account you create here manages Bridge.'
                : 'Sign in to manage messages, knowledge and workflows.' }}
            </p>
          </div>

          <div v-if="creatingOwner">
            <label class="label" for="full-name">Your name</label>
            <input id="full-name" v-model="form.full_name" class="input" autocomplete="name">
          </div>
          <div>
            <label class="label" for="email">Email</label>
            <input id="email" v-model="form.email" type="email" class="input" autocomplete="email" required>
          </div>
          <div>
            <label class="label" for="password">Password</label>
            <input
              id="password" v-model="form.password" type="password" class="input" required
              :minlength="creatingOwner ? 8 : undefined"
              :autocomplete="creatingOwner ? 'new-password' : 'current-password'"
            >
            <p v-if="creatingOwner" class="text-[11px] text-muted mt-1">At least 8 characters.</p>
          </div>
          <div v-if="creatingOwner && setup?.setup_code_required">
            <label class="label" for="setup-code">Setup code</label>
            <input id="setup-code" v-model="form.setup_code" class="input font-mono" autocomplete="off" required>
            <p class="text-[11px] text-muted mt-1">
              The <code class="bg-canvas px-1 rounded">SETUP_CODE</code> value from the backend's environment
              (Render → bridge-api → Environment).
            </p>
          </div>

          <p v-if="error" class="text-xs text-error">{{ error }}</p>

          <button class="btn-primary w-full h-9" :disabled="busy">
            <LogIn class="w-4 h-4" />
            {{ busy ? 'Please wait…' : creatingOwner ? 'Create account' : 'Sign in' }}
          </button>
        </form>
      </div>
      <p class="text-center text-[11px] text-muted mt-4">Bridge: communication across language barriers</p>
    </div>
  </div>
</template>
