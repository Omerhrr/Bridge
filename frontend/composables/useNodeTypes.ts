/** Node registry helpers shared by the builder components. */

import type { NodeSpec, WorkflowDefinition } from "~/types";

export function useNodeTypes() {
  const api = useApi();
  const specs = ref<NodeSpec[]>([]);

  onMounted(async () => {
    try {
      specs.value = await api.get<NodeSpec[]>("/api/node-types");
    } catch {
      specs.value = [];
    }
  });

  const byType = computed(() => {
    const map: Record<string, NodeSpec> = {};
    for (const spec of specs.value) map[spec.type] = spec;
    return map;
  });

  const categories = computed(() => {
    const groups: Record<string, NodeSpec[]> = {};
    for (const spec of specs.value) {
      (groups[spec.category] ||= []).push(spec);
    }
    return groups;
  });

  return { specs, byType, categories };
}

export function categoryIconClass(category: string): string {
  return `cat-${category}`;
}

export function statusBadge(status: string): string {
  switch (status) {
    case "completed": return "ok";
    case "failed": return "err";
    case "waiting_input":
    case "running": return "cyan";
    default: return "neutral";
  }
}

export function formatTime(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

/** Position new nodes without overlapping existing ones. */
export function nextPosition(definition: WorkflowDefinition) {
  const xs = definition.nodes.map((n) => n.position?.x ?? 0);
  const maxY = Math.max(0, ...definition.nodes.map((n) => n.position?.y ?? 0));
  return { x: (xs.length ? Math.max(...xs) : 0) + 40, y: maxY };
}
