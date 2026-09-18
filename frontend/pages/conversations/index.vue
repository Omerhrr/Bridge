<script setup lang="ts">
import type { Conversation } from "~/types";

const api = useApi();
const conversations = ref<Conversation[] | null>(null);
const error = ref("");
const channelFilter = ref("");

const filtered = computed(() => {
  if (!conversations.value) return [];
  if (!channelFilter.value) return conversations.value;
  return conversations.value.filter((c) => c.channel === channelFilter.value);
});

onMounted(load);

async function load() {
  try {
    conversations.value = await api.get<Conversation[]>("/api/conversations");
  } catch {
    error.value = "Could not reach the Bridge API.";
  }
}
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">Conversations</h1>
        <p class="page-sub">Every communication session recorded with its full context (spec §27).</p>
      </div>
      <select v-model="channelFilter" style="width: 150px">
        <option value="">All channels</option>
        <option value="voice">Voice</option>
        <option value="sms">SMS</option>
        <option value="ussd">USSD</option>
      </select>
    </div>

    <div v-if="error" class="error-box">{{ error }}</div>
    <div v-else-if="conversations === null" class="skeleton card card-pad">Loading…</div>
    <div v-else-if="filtered.length === 0" class="empty card">
      No conversations yet — send an SMS to your Africa's Talking number to see one appear here.
    </div>

    <div v-else class="card">
      <table>
        <thead>
          <tr><th>#</th><th>From</th><th>Channel</th><th>Languages</th><th>Status</th><th>Started</th><th>Duration</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="conversation in filtered" :key="conversation.id">
            <td class="muted">{{ conversation.id }}</td>
            <td class="mono">{{ conversation.from_number }}</td>
            <td><span :class="conversation.channel === 'voice' ? 'badge info' : 'badge cyan'">{{ conversation.channel }}</span></td>
            <td class="muted">{{ conversation.language || "?" }} → {{ conversation.target_language || "?" }}</td>
            <td>
              <span class="badge" :class="conversation.status === 'completed' ? 'ok' : conversation.status === 'failed' ? 'err' : 'cyan'">
                {{ conversation.status }}
              </span>
            </td>
            <td class="muted">{{ formatTime(conversation.started_at) }}</td>
            <td class="muted">{{ conversation.duration_ms ? (conversation.duration_ms / 1000).toFixed(1) + "s" : "—" }}</td>
            <td><NuxtLink :to="`/conversations/${conversation.id}`">Timeline</NuxtLink></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
