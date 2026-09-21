<script setup lang="ts">
import { ArrowLeft } from 'lucide-vue-next'
import type { WorkflowRun } from '~/types'

definePageMeta({ layout: 'default' })

const route = useRoute()
const api = useApi()
const store = useWorkflowsStore()

const run = ref<WorkflowRun | null>(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  await store.fetchNodeTypes()
  try {
    run.value = await api<WorkflowRun>(`/runs/${route.params.id}`)
  } catch {
    error.value = 'Could not load this run.'
  } finally {
    loading.value = false
  }
})

const steps = computed(() => {
  if (!run.value) return []
  const out: Array<{ nodeId: string; label: string; ok: boolean; payload: Record<string, unknown> }> = []
  for (const event of run.value.events) {
    if (event.event !== 'node.completed') continue
    if (!event.node_id) continue
    const meta = store.nodeTypes.find((n) => n.type === event.node_type)
    const detailEvent = run.value!.events.find(
      (e) => e.node_id === event.node_id && e.event !== 'node.started' && e.event !== 'node.completed' && e.node_type === event.node_type,
    )
    out.push({
      nodeId: event.node_id,
      label: meta?.label ?? event.node_type ?? event.node_id,
      ok: true,
      payload: detailEvent?.payload ?? {},
    })
  }
  return out
})

function formatWhen(value: string) {
  return new Date(value).toLocaleString()
}
</script>

<template>
  <div>
    <NuxtLink to="/runs" class="btn-ghost mb-3 -ml-3">
      <ArrowLeft class="w-4 h-4" :stroke-width="1.8" /> Runs
    </NuxtLink>

    <p v-if="error" class="card p-4 text-sm text-error bg-error-soft border-error/40">{{ error }}</p>
    <div v-if="loading" class="card p-6 h-64 animate-pulse" />

    <template v-else-if="run">
      <div class="card p-5 mb-4">
        <div class="flex items-center gap-3 flex-wrap">
          <h1 class="text-lg font-semibold tracking-tight tabular-nums">{{ run.id }}</h1>
          <span :class="run.status === 'completed' ? 'pill-success' : run.status === 'failed' ? 'pill-error' : 'pill-neutral'">
            {{ run.status }}
          </span>
        </div>
        <p class="text-sm text-muted mt-1">
          started {{ formatWhen(run.started_at) }}
          <template v-if="run.finished_at"> · finished {{ formatWhen(run.finished_at) }}</template>
        </p>
        <p v-if="run.error" class="text-sm text-error bg-error-soft rounded-md p-2 mt-3">{{ run.error }}</p>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <!-- Node execution history (spec section 29) -->
        <section class="card p-5">
          <h2 class="text-sm font-semibold mb-3">Node execution</h2>
          <ul v-if="steps.length" class="space-y-2">
            <li v-for="step in steps" :key="step.nodeId" class="flex items-baseline gap-2">
              <span class="text-success shrink-0">✓</span>
              <span class="text-sm font-medium">{{ step.label }}</span>
              <span class="text-xs text-muted truncate">
                {{ Object.entries(step.payload).slice(0, 2).map(([k, v]) => `${k}: ${String(v)}`).join(' · ') }}
              </span>
            </li>
          </ul>
          <p v-else class="text-sm text-muted">No node executions recorded.</p>
        </section>

        <!-- Variables -->
        <section class="card p-5">
          <h2 class="text-sm font-semibold mb-3">Run variables</h2>
          <pre class="text-xs bg-canvas rounded-md p-3 overflow-x-auto thin-scroll text-ink/80">{{ run.variables }}</pre>
        </section>
      </div>
    </template>
  </div>
</template>
