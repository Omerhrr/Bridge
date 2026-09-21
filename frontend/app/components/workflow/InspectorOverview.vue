<script setup lang="ts">
import { Info } from 'lucide-vue-next'

/** Inspector placeholder shown when no node is selected. */
const props = defineProps<{ workflow?: { name: string; description: string; status: string } | null }>()
</script>

<template>
  <div class="card p-4 flex-1">
    <div class="flex items-center gap-2 mb-2">
      <Info class="w-4 h-4 text-signal" :stroke-width="1.8" />
      <h3 class="text-sm font-semibold">Builder tips</h3>
    </div>
    <ul class="text-sm text-muted space-y-2 list-disc pl-4">
      <li>Drag a node from the palette onto the canvas.</li>
      <li>Connect nodes by dragging from the right handle to the next node.</li>
      <li>Select a node to configure it here — the inspector changes per node type.</li>
      <li>Run <span class="font-medium text-ink">Validate</span> to catch problems, then <span class="font-medium text-ink">Deploy</span> to make the workflow live.</li>
      <li>Use <span class="font-medium text-ink">Test</span> to simulate a trigger and trace every step.</li>
    </ul>
  </div>
</template>
