<script setup lang="ts">
/** Right inspector: edit the selected node's configuration (spec §22). */
import type { NodeSpec, WorkflowNode } from "~/types";

const props = defineProps<{
  node: WorkflowNode | null;
  spec: NodeSpec | null;
}>();

const emit = defineEmits<{
  (e: "update", config: Record<string, unknown>): void;
  (e: "delete"): void;
}>();

function defaultValue(field: { type: string; default: unknown }) {
  return field.type === "boolean" ? Boolean(field.default) : (field.default ?? "");
}

onMounted(() => {
  if (props.node && props.spec) {
    const config = { ...props.node.config };
    for (const field of props.spec.config_fields) {
      if (config[field.name] === undefined) config[field.name] = defaultValue(field);
    }
    emit("update", config);
  }
});
</script>

<template>
  <div class="inspector card">
    <div v-if="!node || !spec" class="empty">
      Select a node to configure it.
    </div>
    <template v-else>
      <div class="section-title">{{ spec.icon }} {{ spec.label }}</div>
      <p class="muted" style="font-size: 12px; margin: 0 0 1rem">{{ spec.description }}</p>

      <div v-for="field in spec.config_fields" :key="field.name" class="inspector-field">
        <label>{{ field.label }} <span v-if="field.required" style="color: var(--error)">*</span></label>

        <select
          v-if="field.type === 'select'"
          :value="(node.config[field.name] as string) ?? ''"
          @change="emit('update', { ...node.config, [field.name]: ($event.target as HTMLSelectElement).value })"
        >
          <option v-for="option in field.options" :key="option" :value="option">{{ option }}</option>
        </select>

        <textarea
          v-else-if="field.type === 'textarea'"
          rows="3"
          :placeholder="field.placeholder"
          :value="(node.config[field.name] as string) ?? ''"
          @input="emit('update', { ...node.config, [field.name]: ($event.target as HTMLTextAreaElement).value })"
        />

        <label v-else-if="field.type === 'boolean'" style="display: flex; gap: 0.5rem; align-items: center; font-weight: 400">
          <input
            type="checkbox"
            style="width: auto"
            :checked="Boolean(node.config[field.name])"
            @change="emit('update', { ...node.config, [field.name]: ($event.target as HTMLInputElement).checked })"
          />
          Enabled
        </label>

        <input
          v-else
          :type="field.type === 'number' ? 'number' : 'text'"
          :placeholder="field.placeholder"
          :value="(node.config[field.name] as string | number) ?? ''"
          @input="emit('update', { ...node.config, [field.name]: ($event.target as HTMLInputElement).value })"
        />
      </div>

      <button class="ghost-danger" style="margin-top: 1rem; width: 100%" @click="emit('delete')">
        Delete node
      </button>
    </template>
  </div>
</template>
