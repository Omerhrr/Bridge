<script setup lang="ts">
/** Dashboard (spec §19): is Bridge working? what happened? what's active? failures? */
import type { Stats } from "~/types";

const api = useApi();
const stats = ref<Stats | null>(null);
const error = ref("");

onMounted(load);

async function load() {
  try {
    stats.value = await api.get<Stats>("/api/stats");
    error.value = "";
  } catch {
    error.value = "Could not reach the Bridge API. Start it with: uvicorn app.main:app --reload";
  }
}

const statusLabel = computed(() => {
  if (!stats.value) return "…";
  if (stats.value.failed_runs > 0) return "degraded";
  return "OK";
});

function channelBadge(channel: string) {
  return channel === "voice" ? "badge info" : "badge cyan";
}
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">Dashboard</h1>
        <p class="page-sub">System overview across telecom channels and workflows.</p>
      </div>
      <span class="badge" :class="statusLabel === 'OK' ? 'ok' : 'warn'">
        <span class="dot" :class="statusLabel === 'OK' ? 'ok' : 'warn'" /> Status: {{ statusLabel }}
      </span>
    </div>

    <div v-if="error" class="error-box">{{ error }}</div>
    <div v-else-if="!stats" class="skeleton card card-pad">Loading…</div>

    <template v-else>
      <div class="stat-grid">
        <div class="card card-pad">
          <div class="stat-label">Calls</div>
          <div class="stat-value">{{ stats.calls.toLocaleString() }}</div>
          <div class="stat-hint muted">voice conversations</div>
        </div>
        <div class="card card-pad">
          <div class="stat-label">SMS</div>
          <div class="stat-value">{{ stats.sms.toLocaleString() }}</div>
          <div class="stat-hint muted">message conversations</div>
        </div>
        <div class="card card-pad">
          <div class="stat-label">Workflows</div>
          <div class="stat-value">{{ stats.active_workflows }}<span class="muted" style="font-size: 15px"> / {{ stats.total_workflows }}</span></div>
          <div class="stat-hint muted">active / total</div>
        </div>
        <div class="card card-pad">
          <div class="stat-label">Success rate</div>
          <div class="stat-value" :style="{ color: (stats.success_rate ?? 100) >= 95 ? 'var(--success)' : 'var(--warning)' }">
            {{ stats.success_rate !== null ? stats.success_rate + "%" : "—" }}
          </div>
          <div class="stat-hint muted">{{ stats.total_runs }} runs · {{ stats.failed_runs }} failed</div>
        </div>
      </div>

      <div class="grid-2" style="margin-top: 1rem">
        <div class="card">
          <div class="card-pad" style="padding-bottom: 0.4rem">
            <div class="section-title" style="margin-bottom: 0.4rem">Recent communication</div>
          </div>
          <div class="card-pad" style="padding-top: 0">
            <div v-if="stats.recent_conversations.length === 0" class="empty">
              No communication yet — trigger a workflow by calling or texting.
            </div>
            <table v-else>
              <thead>
                <tr><th>From</th><th>Channel</th><th>Languages</th><th>Status</th><th></th></tr>
              </thead>
              <tbody>
                <tr v-for="conversation in stats.recent_conversations" :key="conversation.id">
                  <td class="mono">{{ conversation.from_number }}</td>
                  <td><span :class="channelBadge(conversation.channel)">{{ conversation.channel }}</span></td>
                  <td class="muted">{{ conversation.language || "?" }} → {{ conversation.target_language || "?" }}</td>
                  <td>
                    <span class="badge" :class="conversation.status === 'completed' ? 'ok' : conversation.status === 'failed' ? 'err' : 'cyan'">
                      {{ conversation.status }}
                    </span>
                  </td>
                  <td><NuxtLink :to="`/conversations/${conversation.id}`">View</NuxtLink></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-pad" style="padding-bottom: 0.4rem">
            <div class="section-title" style="margin-bottom: 0.4rem">Workflow activity</div>
          </div>
          <div class="card-pad" style="padding-top: 0">
            <div v-if="stats.workflow_activity.length === 0" class="empty">No workflows configured.</div>
            <table v-else>
              <thead>
                <tr><th>Workflow</th><th>Runs</th><th>Success</th><th></th></tr>
              </thead>
              <tbody>
                <tr v-for="activity in stats.workflow_activity" :key="activity.workflow_id">
                  <td style="font-weight: 550">{{ activity.name }}</td>
                  <td>{{ activity.runs }}</td>
                  <td>
                    <span v-if="activity.success_rate !== null" :class="(activity.success_rate ?? 0) >= 95 ? 'badge ok' : 'badge warn'">
                      {{ activity.success_rate }}%
                    </span>
                    <span v-else class="muted">—</span>
                  </td>
                  <td><NuxtLink :to="`/workflows/${activity.workflow_id}`">Open</NuxtLink></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
