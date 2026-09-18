<script setup lang="ts">
/** Run detail: node execution history + variables + errors (spec §29). */
import type { WorkflowRun } from "~/types";

const route = useRoute();
const api = useApi();
const run = ref<WorkflowRun | null>(null);
const error = ref("");
const showVariables = ref(false);

onMounted(load);

async function load() {
  try {
    run.value = await api.get<WorkflowRun>(`/api/runs/${route.params.id}`);
  } catch {
    error.value = "Could not load this run.";
  }
}

function eventSummary(detail: Record<string, unknown>): string {
  const parts: string[] = [];
  if (detail.transcript) parts.push(`"${detail.transcript}"`);
  if (detail.translated) parts.push(`→ "${detail.translated}"`);
  if (detail.audio_url) parts.push(String(detail.audio_url));
  if (detail.message && detail.to) parts.push(`SMS to ${detail.to}`);
  if (detail.error) parts.push(String(detail.error));
  return parts.join("  ");
}
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <NuxtLink to="/runs" class="muted" style="font-size: 12.5px">← All runs</NuxtLink>
        <h1 class="page-title mono" style="margin-top: 0.2rem">{{ run?.id || "…" }}</h1>
        <p v-if="run" class="page-sub">
          {{ run.workflow_name }} · v{{ run.version }}
          <span class="badge" :class="statusBadge(run.status)" style="margin-left: 0.35rem">{{ run.status }}</span>
          <span v-if="run.duration_ms" class="badge neutral" style="margin-left: 0.35rem">{{ (run.duration_ms / 1000).toFixed(1) }}s</span>
        </p>
      </div>
      <button v-if="run" @click="showVariables = !showVariables">
        {{ showVariables ? "Hide variables" : "Show variables" }}
      </button>
    </div>

    <div v-if="error" class="error-box">{{ error }}</div>

    <template v-else-if="run">
      <div v-if="run.error" class="error-box" style="margin-bottom: 0.9rem">
        <strong>Run failed:</strong> {{ run.error }}
      </div>

      <div class="grid-2" :style="!showVariables ? { gridTemplateColumns: '1fr' } : {}">
        <div class="card card-pad">
          <div class="section-title">Node execution history</div>
          <div v-if="run.events.length === 0" class="empty">No nodes executed.</div>
          <div v-for="event in run.events" :key="event.id" class="trace-row">
            <span class="trace-icon">{{ event.status === "completed" ? "✓" : event.status === "failed" ? "✕" : "⏳" }}</span>
            <span style="flex: 1">
              <strong>{{ event.node_label || event.node_type }}</strong>
              <span class="muted" style="margin-left: 0.4rem">node {{ event.node_id }}</span>
              <div v-if="eventSummary(event.detail)" class="muted mono" style="margin-top: 0.1rem; font-size: 11.5px">
                {{ eventSummary(event.detail) }}
              </div>
            </span>
            <span class="badge" :class="event.status === 'completed' ? 'ok' : event.status === 'failed' ? 'err' : 'cyan'">
              {{ event.status }}
            </span>
          </div>
        </div>

        <div v-if="showVariables" class="card card-pad">
          <div class="section-title">Run variables</div>
          <pre class="mono" style="margin: 0; white-space: pre-wrap; word-break: break-word">{{ JSON.stringify(run.variables, null, 2) }}</pre>
        </div>
      </div>
    </template>
    <div v-else class="skeleton card card-pad">Loading…</div>
  </div>
</template>
