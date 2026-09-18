<script setup lang="ts">
import type { WorkflowRun } from "~/types";

const api = useApi();
const runs = ref<WorkflowRun[] | null>(null);
const error = ref("");
const statusFilter = ref("");

const filtered = computed(() => {
  if (!runs.value) return [];
  if (!statusFilter.value) return runs.value;
  return runs.value.filter((r) => r.status === statusFilter.value);
});

onMounted(load);

async function load() {
  try {
    runs.value = await api.get<WorkflowRun[]>("/api/runs");
  } catch {
    error.value = "Could not reach the Bridge API.";
  }
}
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">Workflow runs</h1>
        <p class="page-sub">Execution history — what ran, on which version, and what happened (spec §29).</p>
      </div>
      <select v-model="statusFilter" style="width: 170px">
        <option value="">All statuses</option>
        <option value="completed">Completed</option>
        <option value="failed">Failed</option>
        <option value="waiting_input">Waiting input</option>
        <option value="running">Running</option>
      </select>
    </div>

    <div v-if="error" class="error-box">{{ error }}</div>
    <div v-else-if="runs === null" class="skeleton card card-pad">Loading…</div>
    <div v-else-if="filtered.length === 0" class="empty card">No runs recorded yet.</div>

    <div v-else class="card">
      <table>
        <thead>
          <tr><th>Run</th><th>Workflow</th><th>Version</th><th>Status</th><th>Duration</th><th>Started</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="run in filtered" :key="run.id">
            <td class="mono">{{ run.id }}</td>
            <td style="font-weight: 550">{{ run.workflow_name || "—" }}</td>
            <td class="muted">v{{ run.version ?? "?" }}</td>
            <td><span class="badge" :class="statusBadge(run.status)">{{ run.status }}</span></td>
            <td class="muted">{{ run.duration_ms ? (run.duration_ms / 1000).toFixed(1) + "s" : "—" }}</td>
            <td class="muted">{{ formatTime(run.started_at) }}</td>
            <td><NuxtLink :to="`/runs/${run.id}`">Trace</NuxtLink></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
