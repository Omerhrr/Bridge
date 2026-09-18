<script setup lang="ts">
/** Workflow builder (spec §20): palette | Vue Flow canvas | inspector. */
import type { NodeSpec, ValidationReport, Workflow, WorkflowDefinition } from "~/types";

const route = useRoute();
const api = useApi();
const { byType } = useNodeTypes();

const workflow = ref<Workflow | null>(null);
const definition = ref<WorkflowDefinition>({ nodes: [], edges: [] });
const selectedId = ref<string | null>(null);
const report = ref<ValidationReport | null>(null);
const saving = ref(false);
const dirty = ref(false);
const error = ref("");

const selectedNode = computed(() => definition.value.nodes.find((n) => n.id === selectedId.value) ?? null);
const selectedSpec = computed<NodeSpec | null>(() => (selectedNode.value ? byType.value[selectedNode.value.type] ?? null : null));

onMounted(async () => {
  try {
    workflow.value = await api.get<Workflow>(`/api/workflows/${route.params.id}`);
    definition.value = workflow.value.definition;
  } catch (e) {
    error.value = "Could not load workflow.";
  }
});

function addNode(type: string) {
  const id = `${type}_${Math.random().toString(36).slice(2, 6)}`;
  const maxY = Math.max(0, ...definition.value.nodes.map((n) => n.position?.y ?? 0));
  definition.value.nodes.push({
    id,
    type,
    position: { x: 60, y: maxY + 30 },
    config: {},
  });
  dirty.value = true;
  selectedId.value = id;
}

function updateDefinition(next: WorkflowDefinition) {
  // Position-only changes should not clobber config edits mid-flight.
  definition.value = next;
  dirty.value = true;
}

function updateSelectedConfig(config: Record<string, unknown>) {
  if (!selectedNode.value) return;
  selectedNode.value.config = config;
  dirty.value = true;
}

function deleteSelected() {
  if (!selectedNode.value) return;
  const id = selectedNode.value.id;
  definition.value.nodes = definition.value.nodes.filter((n) => n.id !== id);
  definition.value.edges = definition.value.edges.filter((e) => e.source !== id && e.target !== id);
  selectedId.value = null;
  dirty.value = true;
}

async function save(silent = false) {
  if (!workflow.value) return;
  saving.value = true;
  error.value = "";
  try {
    workflow.value = await api.put<Workflow>(`/api/workflows/${workflow.value.id}`, { definition: definition.value });
    dirty.value = false;
    if (!silent) report.value = null;
  } catch (e) {
    error.value = "Save failed — is the API running?";
  } finally {
    saving.value = false;
  }
}

async function validate() {
  if (!workflow.value) return;
  await save(true);
  try {
    report.value = await api.post<ValidationReport>(`/api/workflows/${workflow.value.id}/validate`);
  } catch {
    error.value = "Validation request failed.";
  }
}

async function deploy() {
  if (!workflow.value) return;
  await save(true);
  saving.value = true;
  try {
    workflow.value = await api.post<Workflow>(
      `/api/workflows/${workflow.value.id}/deploy`,
      definition.value,
    );
    report.value = null;
    dirty.value = false;
  } catch (e: unknown) {
    const err = e as { data?: { detail?: { report?: ValidationReport } | string } };
    const detail = err.data?.detail;
    if (detail && typeof detail === "object" && "report" in detail) {
      report.value = (detail as { report: ValidationReport }).report;
    } else {
      error.value = typeof detail === "string" ? detail : "Deploy failed.";
    }
  } finally {
    saving.value = false;
  }
}

async function toggleEnabled(enabled: boolean) {
  if (!workflow.value) return;
  workflow.value = await api.put<Workflow>(`/api/workflows/${workflow.value.id}`, { enabled });
}
</script>

<template>
  <div class="page" style="max-width: none">
    <div v-if="error" class="error-box" style="margin-bottom: 0.9rem">{{ error }}</div>

    <template v-if="workflow">
      <WorkflowToolbar
        v-model:report="report"
        :workflow="workflow"
        :saving="saving"
        :dirty="dirty"
        @save="save()"
        @validate="validate()"
        @deploy="deploy()"
        @toggle-enabled="toggleEnabled"
        @select-node="selectedId = $event"
      />

      <div class="builder">
        <NodePalette @add="addNode" />
        <WorkflowCanvas
          :definition="definition"
          :selected-id="selectedId"
          @update="updateDefinition"
          @select="selectedId = $event"
        />
        <WorkflowInspector
          :node="selectedNode"
          :spec="selectedSpec"
          @update="updateSelectedConfig"
          @delete="deleteSelected"
        />
      </div>
    </template>
    <div v-else class="skeleton card card-pad">Loading workflow…</div>
  </div>
</template>
