<script setup lang="ts">
/** Left palette: every registered node type grouped by category (spec §20). */
const { categories } = useNodeTypes();

const emit = defineEmits<{ (e: "add", nodeType: string): void }>();
</script>

<template>
  <div class="palette card">
    <div v-if="Object.keys(categories).length === 0" class="skeleton">Loading nodes…</div>
    <div v-for="(specs, category) in categories" :key="category" class="palette-group">
      <div class="palette-group-title">{{ category }}</div>
      <button
        v-for="spec in specs"
        :key="spec.type"
        class="palette-node"
        :title="spec.description"
        @click="emit('add', spec.type)"
      >
        <span class="node-cat-icon" :class="categoryIconClass(spec.category)">{{ spec.icon }}</span>
        {{ spec.label }}
      </button>
    </div>
  </div>
</template>
