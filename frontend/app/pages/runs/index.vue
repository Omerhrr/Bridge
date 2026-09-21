<script setup lang="ts">
import type { WorkflowRun } from '~/types'

definePageMeta({ layout: 'default' })

const api = useApi()
const store = useWorkflowsStore()
const runs = ref<WorkflowRun[]>([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const [runData] = await Promise.all([api<WorkflowRun[]>('/runs'), store.fetchList()])
    runs.value = runData
  } catch {
    error.value = 'Could not load workflow runs.'
  } finally {
    loading.value = false
  }
})

function workflowName(workflowId: number) {
  return store.list.find((w) => w.id === workflowId)?.name ?? `Workflow #${workflowId}`
}
</script>

<template>
  <div>
    <div class="mb-5">
      <h1 class="text-xl font-semibold tracking-tight">Workflow Runs</h1>
      <p class="text-sm text-muted mt-0.5">Execution history — what ran, when, and whether it succeeded</p>
    </div>

    <p v-if="error" class="card p-4 text-sm text-error bg-error-soft border-error/40 mb-4">{{ error }}</p>

    <div v-if="loading" class="space-y-3">
      <div v-for="i in 4" :key="i" class="card p-4 h-16 animate-pulse" />
    </div>

    <div v-else-if="runs.length" class="card divide-y divide-line">
      <NuxtLink
        v-for="run in runs"
        :key="run.id"
        :to="`/runs/${run.id}`"
        class="px-5 py-3.5 flex items-center gap-3 hover:bg-canvas/60 transition-colors"
      >
        <div class="min-w-0 flex-1">
          <p class="text-sm font-medium">{{ workflowName(run.workflow_id) }}</p>
          <p class="text-xs text-muted mt-0.5 tabular-nums">{{ run.id }} · started {{ new Date(run.started_at).toLocaleTimeString() }}</p>
        </div>
        <span
          :class="run.status === 'completed' ? 'pill-success' : run.status === 'failed' ? 'pill-error' : run.status === 'running' ? 'pill-comms' : 'pill-neutral'"
        >
          {{ run.status }}
        </span>
      </NuxtLink>
    </div>

    <div v-else class="card p-12 text-center">
      <p class="text-sm font-medium">No runs yet</p>
      <p class="text-sm text-muted mt-1">Run a workflow test or trigger it from a phone.</p>
      <NuxtLink to="/workflows" class="btn-primary mt-3">Open workflows</NuxtLink>
    </div>
  </div>
</template>
