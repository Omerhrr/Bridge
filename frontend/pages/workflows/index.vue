<script setup lang="ts">
import type { Workflow } from "~/types";

const api = useApi();
const workflows = ref<Workflow[] | null>(null);
const error = ref("");

onMounted(load);

async function load() {
  try {
    workflows.value = await api.get<Workflow[]>("/api/workflows");
  } catch {
    error.value = "Could not reach the Bridge API. Is the backend running on port 8000?";
  }
}

async function toggle(workflow: Workflow) {
  const updated = await api.put<Workflow>(`/api/workflows/${workflow.id}`, { enabled: !workflow.enabled });
  Object.assign(workflow, updated);
}

async function remove(workflow: Workflow) {
  if (!confirm(`Delete workflow "${workflow.name}"? Its history will be removed.`)) return;
  await api.del(`/api/workflows/${workflow.id}`);
  await load();
}
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">Workflows</h1>
        <p class="page-sub">Communication logic as visual, versioned graphs (spec §10, §31).</p>
      </div>
    </div>

    <div v-if="error" class="error-box">{{ error }}</div>
    <div v-else-if="workflows === null" class="skeleton card card-pad">Loading…</div>
    <div v-else-if="workflows.length === 0" class="empty card">No workflows yet.</div>

    <div v-else class="grid-2">
      <div v-for="workflow in workflows" :key="workflow.id" class="card card-pad">
        <div style="display: flex; align-items: flex-start; gap: 0.7rem">
          <div style="flex: 1">
            <NuxtLink :to="`/workflows/${workflow.id}`" style="font-weight: 600; font-size: 15px">
              {{ workflow.name }}
            </NuxtLink>
            <p class="muted" style="margin: 0.25rem 0 0.5rem; font-size: 12.5px">{{ workflow.description }}</p>
            <div style="display: flex; gap: 0.35rem; flex-wrap: wrap">
              <span :class="workflow.enabled ? 'badge ok' : 'badge neutral'">
                {{ workflow.enabled ? "Active" : "Disabled" }}
              </span>
              <span class="badge info">v{{ workflow.current_version }}</span>
              <span class="badge cyan">{{ workflow.definition.nodes.length }} nodes</span>
            </div>
          </div>
          <button class="toggle" :class="{ on: workflow.enabled }" :aria-label="'Toggle ' + workflow.name" @click="toggle(workflow)" />
        </div>
        <div style="display: flex; gap: 0.5rem; margin-top: 0.9rem">
          <NuxtLink :to="`/workflows/${workflow.id}`"><button>Edit</button></NuxtLink>
          <button class="ghost-danger" @click="remove(workflow)">Delete</button>
        </div>
      </div>
    </div>
  </div>
</template>
