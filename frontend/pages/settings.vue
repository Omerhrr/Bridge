<script setup lang="ts">
/** Settings: provider configuration status + telecom webhook URLs (spec §32, §35). */

const { get } = useApi();
const health = ref<Record<string, unknown> | null>(null);
const error = ref("");

onMounted(async () => {
  try {
    health.value = await get<Record<string, unknown>>("/api/health");
  } catch {
    error.value = "Could not reach the Bridge API.";
  }
});

const baseUrl = typeof window !== "undefined" ? window.location.origin : "";
const webhookUrls = computed(() => [
  { label: "Voice webhook", path: "/webhooks/africastalking/voice" },
  { label: "SMS webhook", path: "/webhooks/africastalking/sms" },
]);
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1 class="page-title">Settings</h1>
        <p class="page-sub">Provider configuration and telecom integration endpoints (spec §25, §35).</p>
      </div>
    </div>

    <div v-if="error" class="error-box">{{ error }}</div>

    <template v-else>
      <div class="card card-pad" style="margin-bottom: 0.9rem">
        <div class="section-title">System status</div>
        <table>
          <tbody>
            <tr><td class="muted">Service</td><td class="mono">bridge-api v{{ health?.version ?? "?" }}</td></tr>
            <tr><td class="muted">Environment</td><td class="mono">{{ health?.environment ?? "—" }}</td></tr>
            <tr>
              <td class="muted">Telecom provider</td>
              <td>
                <span :class="health?.comms_provider === 'africastalking' ? 'badge ok' : 'badge warn'">
                  {{ health?.comms_provider ?? "—" }}
                </span>
                <span v-if="health?.comms_provider === 'mock'" class="muted" style="margin-left: 0.5rem; font-size: 12px">
                  set BRIDGE_AT_USERNAME / BRIDGE_AT_API_KEY to go live
                </span>
              </td>
            </tr>
            <tr>
              <td class="muted">AI provider</td>
              <td>
                <span class="badge info">{{ health?.ai_provider ?? "—" }}</span>
                <span v-if="health?.ai_provider === 'mock'" class="muted" style="margin-left: 0.5rem; font-size: 12px">
                  demo dictionaries (en ↔ ha / sw); plug real providers in app/modules/ai
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card card-pad" style="margin-bottom: 0.9rem">
        <div class="section-title">Africa's Talking webhook URLs</div>
        <p class="muted" style="font-size: 12.5px; margin-top: 0">
          Configure these in your Africa's Talking dashboard. The backend must be
          reachable over public HTTPS (Render, spec §35).
        </p>
        <table>
          <tbody>
            <tr v-for="webhook in webhookUrls" :key="webhook.path">
              <td class="muted" style="width: 180px">{{ webhook.label }}</td>
              <td class="mono">{{ baseUrl }}{{ webhook.path }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card card-pad">
        <div class="section-title">Security (spec §32)</div>
        <ul class="muted" style="font-size: 13px; padding-left: 1.1rem; margin: 0; line-height: 1.8">
          <li>Set <span class="mono">BRIDGE_API_TOKEN</span> to require a bearer token on workflow mutations.</li>
          <li>Provider credentials live in environment variables — never in workflow definitions.</li>
          <li>Telecom webhook events are idempotent: provider retries never duplicate executions (spec §45).</li>
        </ul>
      </div>
    </template>
  </div>
</template>
