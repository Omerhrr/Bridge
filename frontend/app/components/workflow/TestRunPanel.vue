<script setup lang="ts">
import type { WorkflowEvent, WorkflowRun } from '~/types'

const props = defineProps<{ run: WorkflowRun }>()

const store = useWorkflowsStore()

interface Step {
  nodeId: string
  nodeType: string
  status: 'ok' | 'failed'
  detail: string
}

/** Collapse raw events into one row per node execution (spec section 29). */
const steps = computed<Step[]>(() => {
  const out: Step[] = []
  for (const event of props.run.events) {
    if (event.event !== 'node.completed' && event.event !== 'workflow.failed') continue
    if (!event.node_id) continue
    const meta = store.nodeTypes.find((n) => n.type === event.node_type)
    let detail = ''
    if (event.event === 'node.completed') {
      const relevant = props.run.events.find(
        (e) => e.node_id === event.node_id && e.event !== 'node.started' && e.event !== 'node.completed' && e.node_type === event.node_type,
      )
      if (relevant) detail = Object.entries(relevant.payload).slice(0, 2).map(([k, v]) => `${k}: ${String(v)}`).join(' · ')
    }
    out.push({
      nodeId: event.node_id,
      nodeType: meta?.label ?? event.node_type ?? '',
      status: event.event === 'workflow.failed' ? 'failed' : 'ok',
      detail,
    })
  }
  return out
})

const variableSummary = computed(() => {
  const vars = { ...props.run.variables }
  delete vars.correlation_id
  return vars
})
</script>

<template>
  <div class="card p-4">
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-sm font-semibold">Test Run</h3>
      <span :class="run.status === 'completed' ? 'pill-success' : run.status === 'failed' ? 'pill-error' : run.status === 'waiting' ? 'pill-warning' : 'pill-neutral'">
        {{ run.status === 'waiting' ? 'waiting for input' : run.status }}
      </span>
    </div>

    <p v-if="run.error" class="text-sm text-error bg-error-soft rounded-md p-2 mb-3">{{ run.error }}</p>

    <ul class="space-y-1">
      <li v-for="step in steps" :key="step.nodeId + step.status" class="flex items-baseline gap-2 text-sm">
        <span :class="step.status === 'ok' ? 'text-success' : 'text-error'" class="shrink-0 w-4">✓</span>
        <span class="font-medium">{{ step.nodeType }}</span>
        <span v-if="step.detail" class="text-muted truncate">{{ step.detail }}</span>
      </li>
    </ul>

    <div v-if="Object.keys(variableSummary).length" class="mt-3 pt-3 border-t border-line">
      <p class="label">Run variables</p>
      <pre class="text-xs bg-canvas rounded-md p-2 overflow-x-auto thin-scroll text-ink/80">{{ variableSummary }}</pre>
    </div>
  </div>
</template>
