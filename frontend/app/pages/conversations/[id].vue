<script setup lang="ts">
import { ArrowLeft } from 'lucide-vue-next'
import type { Conversation, TimelineEvent } from '~/types'

definePageMeta({ layout: 'default' })

const route = useRoute()
const api = useApi()

const conversation = ref<Conversation | null>(null)
const timeline = ref<TimelineEvent[]>([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  const id = Number(route.params.id)
  try {
    const [conversationData, timelineData] = await Promise.all([
      api<Conversation>(`/conversations/${id}`),
      api<TimelineEvent[]>(`/conversations/${id}/timeline`),
    ])
    conversation.value = conversationData
    timeline.value = timelineData
  } catch {
    error.value = 'Could not load this conversation.'
  } finally {
    loading.value = false
  }
})

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function detailText(detail: Record<string, unknown>): string {
  const parts: string[] = []
  if (detail.content) parts.push(String(detail.content))
  if (detail.translated) parts.push(String(detail.translated))
  return parts.join(' → ')
}
</script>

<template>
  <div>
    <NuxtLink to="/conversations" class="btn-ghost mb-3 -ml-3">
      <ArrowLeft class="w-4 h-4" :stroke-width="1.8" /> Conversations
    </NuxtLink>

    <p v-if="error" class="card p-4 text-sm text-error bg-error-soft border-error/40">{{ error }}</p>

    <div v-if="loading" class="card p-6 h-64 animate-pulse" />

    <template v-else-if="conversation">
      <!-- Header (spec section 27) -->
      <div class="card p-5 mb-4">
        <div class="flex flex-wrap items-center gap-3">
          <h1 class="text-lg font-semibold tracking-tight">
            {{ conversation.a_number || 'Unknown' }}
            <span class="text-muted mx-1">↔</span>
            {{ conversation.b_number || 'Bridge' }}
          </h1>
          <span :class="conversation.status === 'completed' ? 'pill-success' : conversation.status === 'failed' ? 'pill-error' : 'pill-warning'">
            {{ conversation.status }}
          </span>
        </div>
        <p class="text-sm text-muted mt-1">
          {{ conversation.channel === 'voice' ? 'Voice call' : conversation.channel === 'sms' ? 'SMS exchange' : 'USSD session' }}
          <template v-if="conversation.source_language"> · {{ conversation.source_language }} ↔ {{ conversation.target_language }}</template>
          <template v-if="conversation.workflow_run_id"> · run {{ conversation.workflow_run_id }}</template>
        </p>
      </div>

      <!-- Timeline (spec section 28) -->
      <section class="card p-5">
        <h2 class="text-sm font-semibold mb-4">Session timeline</h2>

        <div v-if="timeline.length" class="space-y-0">
          <div
            v-for="(event, index) in timeline"
            :key="index"
            class="flex gap-3"
          >
            <!-- timeline rail -->
            <div class="flex flex-col items-center">
              <span
                class="w-2.5 h-2.5 rounded-full mt-1.5 shrink-0"
                :class="event.kind === 'message' ? 'bg-signal' : 'bg-comms'"
              />
              <span v-if="index < timeline.length - 1" class="w-px flex-1 bg-line my-1" />
            </div>
            <!-- content -->
            <div class="pb-5 min-w-0">
              <p class="text-xs text-muted tabular-nums">{{ formatTime(event.timestamp) }}</p>
              <p class="text-sm font-medium mt-0.5">{{ event.label }}</p>
              <p v-if="detailText(event.detail)" class="text-sm text-ink/80 mt-0.5">{{ detailText(event.detail) }}</p>
            </div>
          </div>
        </div>

        <p v-else class="text-sm text-muted">No recorded events for this session.</p>
      </section>
    </template>
  </div>
</template>
