<script setup lang="ts">
/** Vue Flow canvas (spec §20). The frontend is the *visual* layer only —
 *  validation and execution live in the backend (spec §10). */
import { VueFlow, type Connection, type Edge, type Node, type NodeMouseEvent } from "@vue-flow/core";
import { Background } from "@vue-flow/background";
import type { WorkflowDefinition } from "~/types";
import BridgeFlowNode from "./nodes/BridgeFlowNode.vue";

const props = defineProps<{
  definition: WorkflowDefinition;
  selectedId: string | null;
}>();

const emit = defineEmits<{
  (e: "update", definition: WorkflowDefinition): void;
  (e: "select", nodeId: string | null): void;
}>();

const nodeTypes = { bridge: BridgeFlowNode };

// Definition -> Vue Flow
function toFlowNodes(): Node[] {
  return props.definition.nodes.map((n) => ({
    id: n.id,
    type: "bridge",
    position: { x: n.position?.x ?? 0, y: n.position?.y ?? 0 },
    data: { nodeType: n.type, label: n.label, config: n.config },
  }));
}

function toFlowEdges(): Edge[] {
  return props.definition.edges.map((e, index) => ({
    id: `e-${e.source}-${e.target}-${index}`,
    source: e.source,
    target: e.target,
    sourceHandle: e.source_handle ?? undefined,
  }));
}

const flowNodes = ref<Node[]>(toFlowNodes());
const flowEdges = ref<Edge[]>(toFlowEdges());

// External definition changes (e.g. node added from the palette) flow in.
watch(
  () => props.definition,
  () => {
    flowNodes.value = toFlowNodes();
    flowEdges.value = toFlowEdges();
  },
  { deep: true },
);

// Vue Flow changes (drag, select) flow out into the definition.
function syncFromFlow() {
  emit("update", {
    nodes: flowNodes.value.map((n) => ({
      id: n.id,
      type: (n.data as { nodeType: string }).nodeType,
      label: (n.data as { label?: string }).label,
      position: { x: Math.round(n.position.x), y: Math.round(n.position.y) },
      config: (n.data as { config: Record<string, unknown> }).config ?? {},
    })),
    edges: flowEdges.value.map((e) => ({
      source: e.source,
      target: e.target,
      source_handle: e.sourceHandle ?? null,
    })),
  });
}

function onConnect(connection: Connection) {
  flowEdges.value.push({
    id: `e-${connection.source}-${connection.target}-${Date.now()}`,
    source: connection.source,
    target: connection.target,
    sourceHandle: connection.sourceHandle ?? undefined,
  });
  syncFromFlow();
}

function onNodeClick({ node }: NodeMouseEvent) {
  emit("select", node.id);
}

function onPaneClick() {
  emit("select", null);
}
</script>

<template>
  <div class="canvas-wrap">
    <ClientOnly>
      <VueFlow
        v-model:nodes="flowNodes"
        v-model:edges="flowEdges"
        :node-types="nodeTypes"
        :default-viewport="{ zoom: 0.85 }"
        :min-zoom="0.3"
        :max-zoom="1.8"
        fit-view-on-init
        @connect="onConnect"
        @node-click="onNodeClick"
        @pane-click="onPaneClick"
        @nodes-change="syncFromFlow"
        @edges-change="syncFromFlow"
      >
        <Background :gap="18" />
      </VueFlow>
      <template #fallback>
        <div class="skeleton">Loading canvas…</div>
      </template>
    </ClientOnly>
  </div>
</template>
