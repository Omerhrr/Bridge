<script setup lang="ts">
/** Compact node visual language (spec §21): what it does, its state, its ports. */
import { Handle, Position } from "@vue-flow/core";
import type { NodeProps } from "@vue-flow/core";
import type { NodeSpec } from "~/types";

const props = defineProps<NodeProps>();

const { byType } = useNodeTypes();
const spec = computed<NodeSpec | undefined>(() => byType.value[props.data?.nodeType ?? props.type ?? ""]);
const missingConfig = computed(() => {
  if (!spec.value) return false;
  return spec.value.config_fields.some(
    (f) => f.required && !(props.data?.config ?? {})[f.name],
  );
});
</script>

<template>
  <div class="bridge-node" :class="{ 'node-error': missingConfig }">
    <Handle v-if="spec && spec.type !== 'incoming_call' && spec.type !== 'incoming_sms' && spec.type !== 'ussd_request' && spec.type !== 'start'" type="target" :position="Position.Left" />
    <div class="bridge-node-head">
      <span class="node-cat-icon" :class="spec ? categoryIconClass(spec.category) : 'cat-flow'">
        {{ spec?.icon ?? "?" }}
      </span>
      <span>{{ props.data?.label ?? spec?.label ?? props.type }}</span>
    </div>
    <div v-if="missingConfig" class="bridge-node-desc" style="color: var(--error)">
      ⚠ Missing required configuration
    </div>
    <div v-else-if="props.data?.summary" class="bridge-node-desc">{{ props.data.summary }}</div>

    <!-- Branch outputs -->
    <template v-if="spec">
      <Handle
        v-for="(output, index) in spec.outputs"
        :key="output"
        :id="output === 'out' ? undefined : output"
        type="source"
        :position="Position.Right"
        :style="{ top: `${14 + index * 16}px` }"
      />
      <div v-if="spec.outputs.length > 1" class="bridge-node-desc" style="text-align: right">
        {{ spec.outputs.join(" · ") }}
      </div>
    </template>
  </div>
</template>
