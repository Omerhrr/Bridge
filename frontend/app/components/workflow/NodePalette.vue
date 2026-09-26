<script setup lang="ts">
import type { NodeMeta } from '~/types'

/** Node palette grouped by category (spec section 20).
 *  variant="panel": fixed desktop side panel; nodes are drag-and-drop.
 *  variant="sheet": mobile bottom sheet; nodes are tap-to-add and emit `add`. */
const props = defineProps<{ variant?: 'panel' | 'sheet' }>()
const emit = defineEmits<{ (e: 'add', type: string): void }>()

const store = useWorkflowsStore()
const search = ref('')

const categories = [
  { key: 'trigger', label: 'Triggers' },
  { key: 'voice', label: 'Voice' },
  { key: 'ai', label: 'AI' },
  { key: 'messaging', label: 'Messaging' },
  { key: 'telecom', label: 'Telecom' },
  { key: 'logic', label: 'Logic' },
  { key: 'flow', label: 'Flow' },
] as const

const grouped = computed(() => {
  const term = search.value.trim().toLowerCase()
  return categories
    .map((category) => ({
      ...category,
      nodes: store.nodeTypes
        .filter((n) => n.category === category.key)
        .filter((n) => !term || n.label.toLowerCase().includes(term) || n.description.toLowerCase().includes(term)),
    }))
    .filter((group) => group.nodes.length)
})

function onDragStart(event: DragEvent, node: NodeMeta) {
  event.dataTransfer?.setData('application/bridge-node', node.type)
  event.dataTransfer!.effectAllowed = 'move'
}
</script>

<template>
  <aside
    class="card flex flex-col overflow-hidden"
    :class="variant === 'sheet' ? 'w-full max-h-[60vh]' : 'w-60 shrink-0'"
  >
    <div class="p-3 border-b border-line">
      <h2 class="text-sm font-semibold mb-2">Nodes</h2>
      <input v-model="search" type="search" placeholder="Search nodes…" class="input h-8 text-sm" />
    </div>
    <div class="flex-1 overflow-y-auto thin-scroll p-3 space-y-4">
      <div v-for="group in grouped" :key="group.key">
        <p class="text-[11px] font-semibold uppercase tracking-wider text-muted mb-1.5">{{ group.label }}</p>
        <div class="space-y-1">
          <div
            v-for="node in group.nodes"
            :key="node.type"
            draggable="true"
            class="p-2 rounded-md border border-line bg-surface hover:border-signal/50 hover:bg-signal-soft/40 cursor-grab active:cursor-grabbing transition-colors"
            :title="node.description"
            @dragstart="onDragStart($event, node)"
            @click="emit('add', node.type)"
          >
            <p class="text-sm font-medium">{{ node.label }}</p>
            <p class="text-[11px] text-muted leading-snug">{{ node.description }}</p>
          </div>
        </div>
      </div>
      <p v-if="!grouped.length && store.nodeTypes.length" class="text-sm text-muted p-2">No nodes match "{{ search }}".</p>
      <p v-if="!store.nodeTypes.length" class="text-sm text-muted p-2">Node library unavailable: backend offline?</p>
    </div>
  </aside>
</template>
