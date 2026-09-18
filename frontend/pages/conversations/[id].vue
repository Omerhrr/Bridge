<script setup lang="ts">
import type { Conversation } from "~/types";

const route = useRoute();
const api = useApi();
const conversation = ref<(Conversation & { messages?: Array<{ id: number; role: string; content: string; translated_content?: string | null; language?: string | null; created_at?: string }> }) | null>(null);
const error = ref("");

onMounted(load);

async function load() {
  try {
    conversation.value = await api.get(`/api/conversations/${route.params.id}`);
  } catch {
    error.value = "Could not load this conversation.";
  }
}
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <NuxtLink to="/conversations" class="muted" style="font-size: 12.5px">← All conversations</NuxtLink>
        <h1 class="page-title" style="margin-top: 0.2rem">
          <span class="mono">{{ conversation?.from_number || "…" }}</span>
        </h1>
        <p v-if="conversation" class="page-sub">
          <span :class="conversation.channel === 'voice' ? 'badge info' : 'badge cyan'">{{ conversation.channel }}</span>
          <span class="badge neutral" style="margin-left: 0.35rem">{{ conversation.language || "?" }} → {{ conversation.target_language || "?" }}</span>
          <span class="badge" :class="conversation.status === 'completed' ? 'ok' : 'cyan'" style="margin-left: 0.35rem">{{ conversation.status }}</span>
        </p>
      </div>
    </div>

    <div v-if="error" class="error-box">{{ error }}</div>

    <div v-else-if="conversation" class="card card-pad">
      <div class="section-title">Communication timeline (spec §28)</div>
      <ul v-if="conversation.messages?.length" class="timeline">
        <li v-for="message in conversation.messages" :key="message.id" :class="message.role">
          <div class="timeline-time">{{ formatTime(message.created_at) }}</div>
          <div class="timeline-role">
            {{ message.role === "user" ? "User" : "Bridge" }}
            <span v-if="message.language" class="badge neutral" style="margin-left: 0.3rem">{{ message.language }}</span>
          </div>
          <div class="timeline-content">{{ message.content }}</div>
          <div v-if="message.translated_content && message.translated_content !== message.content" class="timeline-content muted">
            ↳ {{ message.translated_content }}
          </div>
        </li>
      </ul>
      <div v-else class="empty">No messages recorded in this conversation.</div>
    </div>
    <div v-else class="skeleton card card-pad">Loading…</div>
  </div>
</template>
