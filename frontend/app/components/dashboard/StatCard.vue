<script setup lang="ts">
import { PhoneCall, MessageSquare, Workflow as WorkflowIcon, Gauge } from 'lucide-vue-next'

defineProps<{
  label: string
  value: string | number
  hint?: string
  icon?: 'calls' | 'sms' | 'workflows' | 'success'
  tone?: 'default' | 'success' | 'warning'
}>()

const icons = {
  calls: PhoneCall,
  sms: MessageSquare,
  workflows: WorkflowIcon,
  success: Gauge,
}
</script>

<template>
  <div class="card p-5 flex items-start gap-4">
    <div
      class="grid place-items-center w-10 h-10 rounded-lg shrink-0"
      :class="tone === 'success' ? 'bg-success-soft text-success' : tone === 'warning' ? 'bg-warning-soft text-warning' : 'bg-signal-soft text-signal'"
    >
      <component :is="icons[icon ?? 'workflows']" class="w-5 h-5" :stroke-width="1.8" />
    </div>
    <div class="min-w-0">
      <p class="text-sm text-muted">{{ label }}</p>
      <p class="text-2xl font-semibold tracking-tight mt-0.5 tabular-nums">{{ value }}</p>
      <p v-if="hint" class="text-xs text-muted mt-1">{{ hint }}</p>
    </div>
  </div>
</template>
