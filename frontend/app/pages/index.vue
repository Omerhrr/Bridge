<script setup lang="ts">
import { ref } from 'vue'
import { PhoneCall, MessageSquare, ArrowRight, RefreshCw } from 'lucide-vue-next'
import type { DashboardSummary } from '~/types'

definePageMeta({ layout: 'default' })

const api = useApi()
const summary = ref<DashboardSummary | null>(null)
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    summary.value = await api<DashboardSummary>('/dashboard/summary')
  } catch {
    error.value = 'Could not reach the Bridge backend. Make sure the FastAPI server is running.'
  } finally {
    loading.value = false
  }
}

onMounted(load)

function channelLabel(channel: string) {
  return channel === 'voice' ? 'Voice' : channel === 'sms' ? 'SMS' : 'USSD'
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-5">
      <div>
        <h1 class="text-xl font-semibold tracking-tight">Dashboard</h1>
        <p class="text-sm text-muted mt-0.5">System overview: is Bridge working, and what happened recently</p>
      </div>
      <button class="btn-secondary" @click="load">
        <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': loading }" :stroke-width="1.8" />
        Refresh
      </button>
    </div>

    <!-- Loading skeletons -->
    <div v-if="loading" class="space-y-4">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div v-for="i in 4" :key="i" class="card p-5 animate-pulse">
          <div class="h-10 w-10 rounded-lg bg-canvas mb-3" />
          <div class="h-3 w-16 bg-canvas rounded mb-2" />
          <div class="h-6 w-20 bg-canvas rounded" />
        </div>
      </div>
      <div class="card p-5 h-48 animate-pulse" />
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="card p-6 border-error/40 bg-error-soft">
      <p class="text-sm font-medium text-error">Backend unavailable</p>
      <p class="text-sm text-ink/80 mt-1">{{ error }}</p>
      <button class="btn-primary mt-4" @click="load">Try again</button>
    </div>

    <template v-else-if="summary">
      <!-- Stat cards (spec section 19) -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <DashboardStatCard label="Calls" :value="summary.calls" icon="calls" />
        <DashboardStatCard label="SMS" :value="summary.sms" icon="sms" />
        <DashboardStatCard
          label="Workflows"
          :value="summary.active_workflows"
          :hint="`${summary.total_workflows} total`"
          icon="workflows"
        />
        <DashboardStatCard
          label="Success"
          :value="`${summary.success_rate}%`"
          icon="success"
          :tone="summary.success_rate >= 95 ? 'success' : summary.success_rate >= 80 ? 'default' : 'warning'"
        />
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
        <!-- Recent communication -->
        <section class="card">
          <header class="px-5 py-3.5 border-b border-line flex items-center justify-between">
            <h2 class="text-sm font-semibold">Recent Communication</h2>
            <NuxtLink to="/conversations" class="text-xs text-signal hover:underline">View all</NuxtLink>
          </header>
          <div v-if="summary.recent_conversations.length">
            <div
              v-for="conversation in summary.recent_conversations"
              :key="conversation.id"
              class="px-5 py-3 border-b border-line last:border-0 flex items-center gap-3 hover:bg-canvas/60"
            >
              <span class="grid place-items-center w-8 h-8 rounded-md bg-canvas shrink-0">
                <PhoneCall v-if="conversation.channel === 'voice'" class="w-4 h-4 text-signal" :stroke-width="1.8" />
                <MessageSquare v-else class="w-4 h-4 text-comms" :stroke-width="1.8" />
              </span>
              <NuxtLink :to="`/conversations/${conversation.id}`" class="min-w-0 flex-1 group">
                <p class="text-sm font-medium group-hover:text-signal transition-colors truncate">
                  {{ conversation.a_number || 'Unknown' }}
                  <ArrowRight class="inline w-3.5 h-3.5 mx-1 text-muted" />
                  {{ conversation.b_number || 'Bridge' }}
                </p>
                <p class="text-xs text-muted">
                  {{ channelLabel(conversation.channel) }}
                  <template v-if="conversation.source_language">
                    · {{ conversation.source_language }} → {{ conversation.target_language }}
                  </template>
                </p>
              </NuxtLink>
              <span :class="conversation.status === 'completed' ? 'pill-success' : conversation.status === 'failed' ? 'pill-error' : 'pill-warning'">
                {{ conversation.status }}
              </span>
            </div>
          </div>
          <div v-else class="px-5 py-10 text-center">
            <p class="text-sm text-muted">No communication yet.</p>
            <p class="text-xs text-muted mt-1">Call or text the Bridge number, or run a workflow test.</p>
          </div>
        </section>

        <!-- Workflow activity -->
        <section class="card">
          <header class="px-5 py-3.5 border-b border-line flex items-center justify-between">
            <h2 class="text-sm font-semibold">Workflow Activity</h2>
            <NuxtLink to="/workflows" class="text-xs text-signal hover:underline">Manage</NuxtLink>
          </header>
          <div v-if="summary.workflow_activity.length">
            <div
              v-for="workflow in summary.workflow_activity"
              :key="workflow.id"
              class="px-5 py-3.5 border-b border-line last:border-0"
            >
              <div class="flex items-center gap-2 mb-1.5">
                <NuxtLink :to="`/workflows/${workflow.id}`" class="text-sm font-medium hover:text-signal transition-colors">
                  {{ workflow.name }}
                </NuxtLink>
                <span :class="workflow.status === 'active' ? 'pill-success' : 'pill-neutral'">{{ workflow.status }}</span>
                <span class="ml-auto text-xs text-muted tabular-nums">
                  {{ workflow.runs }} runs · {{ workflow.success_rate }}%
                </span>
              </div>
              <div class="h-1.5 rounded-full bg-canvas overflow-hidden">
                <div
                  class="h-full rounded-full transition-all"
                  :class="workflow.success_rate >= 95 ? 'bg-success' : workflow.success_rate >= 80 ? 'bg-warning' : 'bg-error'"
                  :style="{ width: `${Math.max(workflow.success_rate, 2)}%` }"
                />
              </div>
            </div>
          </div>
          <div v-else class="px-5 py-10 text-center">
            <p class="text-sm text-muted">No workflows yet.</p>
            <NuxtLink to="/workflows" class="btn-primary mt-3">Create a workflow</NuxtLink>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>
