<script setup lang="ts">
const links = [
  { to: "/", label: "Dashboard", icon: "▦" },
  { to: "/workflows", label: "Workflows", icon: "⎇" },
  { to: "/conversations", label: "Conversations", icon: "💬" },
  { to: "/runs", label: "Runs", icon: "⟳" },
  { to: "/settings", label: "Settings", icon: "⚙" },
];

const { get } = useApi();
const health = ref<{ status: string; comms_provider: string } | null>(null);

onMounted(async () => {
  try {
    health.value = await get<{ status: string; comms_provider: string }>("/api/health");
  } catch {
    health.value = null;
  }
});
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">B</div>
        <div>
          <div class="brand-name">Bridge</div>
          <div class="brand-sub">Telecom Automation</div>
        </div>
      </div>
      <nav class="nav">
        <NuxtLink v-for="link in links" :key="link.to" :to="link.to">
          <span class="nav-icon">{{ link.icon }}</span>
          {{ link.label }}
        </NuxtLink>
      </nav>
      <div class="sidebar-footer">
        <template v-if="health">
          <span class="dot ok" /> API online · {{ health.comms_provider }}
        </template>
        <template v-else>
          <span class="dot err" /> API offline
        </template>
      </div>
    </aside>
    <div class="main">
      <slot />
    </div>
  </div>
</template>
