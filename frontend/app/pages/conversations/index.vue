<script setup lang="ts">
import { PhoneCall, MessageSquare, ArrowRight } from 'lucide-vue-next'
import type { Conversation } from '~/types'

definePageMeta({ layout: 'default' })

const api = useApi()
const conversations = ref<Conversation[]>([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    conversations.value = await api<Conversation[]>('/conversations')
  } catch {
    error.value = 'Could not load conversations.'
  } finally {
    loading.value = false
  }
})

function formatWhen(value: string) {
  return new Date(value).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div>
    <div class="mb-5">
      <h1 class="text-xl font-semibold tracking-tight">Conversations</h1>
      <p class="text-sm text-muted mt-0.5">Every communication session through Bridge: calls, SMS and their translations</p>
    </div>

    <p v-if="error" class="card p-4 text-sm text-error bg-error-soft border-error/40 mb-4">{{ error }}</p>

    <div v-if="loading" class="space-y-3">
      <div v-for="i in 4" :key="i" class="card p-4 h-16 animate-pulse" />
    </div>

    <div v-else-if="conversations.length" class="card divide-y divide-line">
      <NuxtLink
        v-for="conversation in conversations"
        :key="conversation.id"
        :to="`/conversations/${conversation.id}`"
        class="px-5 py-3.5 flex items-center gap-3 hover:bg-canvas/60 transition-colors"
      >
        <span class="grid place-items-center w-9 h-9 rounded-md bg-canvas shrink-0">
          <PhoneCall v-if="conversation.channel === 'voice'" class="w-4 h-4 text-signal" :stroke-width="1.8" />
          <MessageSquare v-else class="w-4 h-4 text-comms" :stroke-width="1.8" />
        </span>
        <div class="min-w-0 flex-1">
          <p class="text-sm font-medium flex items-center gap-1">
            {{ conversation.a_number || 'Unknown' }}
            <ArrowRight class="w-3.5 h-3.5 text-muted" />
            {{ conversation.b_number || 'Bridge' }}
          </p>
          <p class="text-xs text-muted mt-0.5">
            {{ conversation.channel === 'voice' ? 'Voice' : conversation.channel === 'sms' ? 'SMS' : 'USSD' }}
            <template v-if="conversation.source_language"> · {{ conversation.source_language }} ↔ {{ conversation.target_language }}</template>
            · {{ formatWhen(conversation.started_at) }}
          </p>
        </div>
        <span :class="conversation.status === 'completed' ? 'pill-success' : conversation.status === 'failed' ? 'pill-error' : 'pill-warning'">
          {{ conversation.status }}
        </span>
      </NuxtLink>
    </div>

    <div v-else class="card p-12 text-center">
      <p class="text-sm font-medium">No conversations yet</p>
      <p class="text-sm text-muted mt-1">
        Call or text the Bridge number, or use the Test button in a workflow to simulate a session.
      </p>
    </div>
  </div>
</template>
