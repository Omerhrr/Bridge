<script setup lang="ts">
import type { ValidationIssue } from '~/types'

defineProps<{
  issues: ValidationIssue[]
  checksPassed: number
}>()

const emit = defineEmits<{ (e: 'select', nodeId: string): void }>()
</script>

<template>
  <div class="card p-4">
    <div class="flex items-center justify-between mb-2">
      <h3 class="text-sm font-semibold">Workflow Validation</h3>
      <span :class="issues.length ? 'pill-warning' : 'pill-success'">
        {{ checksPassed }} checks passed
        <template v-if="issues.length">· {{ issues.length }} issue{{ issues.length > 1 ? 's' : '' }}</template>
      </span>
    </div>
    <ul class="space-y-1.5 max-h-48 overflow-y-auto thin-scroll">
      <li
        v-for="(issue, index) in issues"
        :key="index"
        class="flex items-start gap-2 text-sm"
        :class="issue.node_id ? 'cursor-pointer hover:bg-canvas rounded p-1 -m-1' : 'p-1 -m-1'"
        @click="issue.node_id && emit('select', issue.node_id)"
      >
        <span :class="issue.level === 'error' ? 'text-error' : 'text-warning'" class="mt-0.5 shrink-0">
          {{ issue.level === 'error' ? '✕' : '⚠' }}
        </span>
        <span class="text-ink/90">{{ issue.message }}</span>
      </li>
      <li v-if="!issues.length" class="flex items-center gap-2 text-sm text-success p-1 -m-1">
        <span class="shrink-0">✓</span> All checks passed. This workflow is ready to deploy
      </li>
    </ul>
  </div>
</template>
