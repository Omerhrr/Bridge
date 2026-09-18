<script setup lang="ts">
/** Top toolbar: Save / Validate / Deploy / Enable (spec §20). */
import type { ValidationReport, Workflow } from "~/types";

defineProps<{
  workflow: Workflow;
  saving: boolean;
  dirty: boolean;
}>();

const emit = defineEmits<{
  (e: "save"): void;
  (e: "validate"): void;
  (e: "deploy"): void;
  (e: "toggle-enabled", enabled: boolean): void;
}>();

const report = defineModel<ValidationReport | null>("report");
</script>

<template>
  <div class="toolbar">
    <div style="margin-right: auto">
      <h2 class="page-title">{{ workflow.name }}</h2>
      <p class="page-sub">
        v{{ workflow.current_version }} ·
        <span :class="workflow.enabled ? 'badge ok' : 'badge neutral'">
          {{ workflow.enabled ? "Active" : "Disabled" }}
        </span>
        <span v-if="dirty" class="badge warn" style="margin-left: 0.35rem">Unsaved changes</span>
      </p>
    </div>

    <button :disabled="saving" @click="emit('save')">Save</button>
    <button :disabled="saving" @click="emit('validate')">Validate</button>
    <button class="primary" :disabled="saving" @click="emit('deploy')">Deploy</button>
    <button
      class="toggle"
      :class="{ on: workflow.enabled }"
      :aria-label="workflow.enabled ? 'Disable workflow' : 'Enable workflow'"
      @click="emit('toggle-enabled', !workflow.enabled)"
    />
  </div>

  <div v-if="report" class="card card-pad" style="margin-bottom: 0.9rem">
    <div class="section-title">Workflow validation</div>
    <p style="margin: 0 0 0.5rem; font-size: 13px" :class="report.valid ? '' : 'text-error'">
      <strong :style="{ color: report.valid ? 'var(--success)' : 'var(--error)' }">{{ report.summary }}</strong>
    </p>
    <ul class="validation-list">
      <li
        v-for="(check, index) in report.checks"
        :key="index"
        :class="{ clickable: check.node_id }"
        :title="check.node_id ? 'Jump to node' : ''"
        @click="check.node_id && $emit('select-node', check.node_id)"
      >
        <span>{{ check.severity === "ok" ? "✓" : check.severity === "error" ? "✕" : "⚠" }}</span>
        <span :style="{ color: check.severity === 'error' ? 'var(--error)' : check.severity === 'warning' ? 'var(--warning)' : 'var(--muted)' }">
          {{ check.message }}
        </span>
      </li>
    </ul>
  </div>
</template>
