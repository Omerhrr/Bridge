<script setup lang="ts">
import type { NodeMeta } from '~/types'

/** Right panel: selected node configuration (spec sections 20/22). */
const props = defineProps<{
  node: { id: string; type: string; config: Record<string, unknown>; error?: boolean } | null
}>()

const emit = defineEmits<{
  (e: 'update:config', config: Record<string, unknown>): void
  (e: 'delete'): void
}>()

const store = useWorkflowsStore()

const meta = computed<NodeMeta | undefined>(() =>
  props.node ? store.nodeTypes.find((n) => n.type === props.node!.type) : undefined,
)

function updateField(name: string, value: unknown) {
  if (!props.node) return
  emit('update:config', { ...props.node.config, [name]: value })
}
</script>

<template>
  <aside class="card w-72 shrink-0 flex flex-col overflow-hidden">
    <div class="p-3 border-b border-line flex items-center justify-between">
      <h2 class="text-sm font-semibold">Inspector</h2>
      <button v-if="node" class="btn-ghost text-error hover:bg-error-soft" title="Delete node" @click="emit('delete')">
        Delete
      </button>
    </div>

    <!-- Node configuration (changes per node type, spec section 22) -->
    <div v-if="node && meta" class="flex-1 overflow-y-auto thin-scroll p-3 space-y-3">
      <div>
        <p class="text-sm font-medium">{{ meta.label }}</p>
        <p class="text-xs text-muted mt-0.5">{{ meta.description }}</p>
      </div>

      <div v-for="field in meta.config_schema" :key="field.name">
        <label class="label" :for="`cfg-${field.name}`">
          {{ field.label }}<span v-if="field.required" class="text-error"> *</span>
        </label>

        <select
          v-if="field.type === 'select'"
          :id="`cfg-${field.name}`"
          class="input"
          :value="(node.config[field.name] as string) ?? ''"
          @change="updateField(field.name, ($event.target as HTMLSelectElement).value)"
        >
          <option value="" disabled>Select…</option>
          <option v-for="option in field.options" :key="option" :value="option">{{ option }}</option>
        </select>

        <textarea
          v-else-if="field.type === 'textarea'"
          :id="`cfg-${field.name}`"
          class="input h-20 py-2"
          :value="(node.config[field.name] as string) ?? ''"
          @input="updateField(field.name, ($event.target as HTMLTextAreaElement).value)"
        />

        <input
          v-else-if="field.type === 'number'"
          :id="`cfg-${field.name}`"
          type="number"
          class="input"
          :value="(node.config[field.name] as number) ?? field.default ?? ''"
          @input="updateField(field.name, Number(($event.target as HTMLInputElement).value))"
        />

        <input
          v-else
          :id="`cfg-${field.name}`"
          type="text"
          class="input"
          :placeholder="field.default !== undefined ? String(field.default) : ''"
          :value="(node.config[field.name] as string) ?? ''"
          @input="updateField(field.name, ($event.target as HTMLInputElement).value)"
        />

        <p v-if="field.hint" class="text-[11px] text-muted mt-1">{{ field.hint }}</p>
      </div>
    </div>

    <!-- Workflow overview when nothing is selected -->
    <div v-else class="flex-1 overflow-y-auto thin-scroll p-3">
      <p class="text-sm text-muted leading-relaxed">
        Select a node on the canvas to configure it. Drag nodes from the palette and connect them
        to build a communication workflow.
      </p>
    </div>
  </aside>
</template>
