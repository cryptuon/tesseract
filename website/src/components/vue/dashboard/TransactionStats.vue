<script setup lang="ts">
import { computed } from 'vue';
import type { StatsResponse } from '@lib/api';

interface Props {
  stats: StatsResponse | null;
  detailed?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  detailed: false,
});

const total = computed(() => {
  if (!props.stats) return 0;
  return (
    props.stats.buffered +
    props.stats.ready +
    props.stats.submitted +
    props.stats.finalized +
    props.stats.failed
  );
});

const successRate = computed(() => {
  if (!props.stats || total.value === 0) return 0;
  return ((props.stats.finalized / total.value) * 100).toFixed(1);
});

const statItems = computed(() => [
  {
    label: 'Buffered',
    value: props.stats?.buffered ?? 0,
    color: 'bg-blue-500',
    description: 'Transactions waiting in buffer',
  },
  {
    label: 'Ready',
    value: props.stats?.ready ?? 0,
    color: 'bg-yellow-500',
    description: 'Ready for execution',
  },
  {
    label: 'Submitted',
    value: props.stats?.submitted ?? 0,
    color: 'bg-purple-500',
    description: 'Submitted to chain',
  },
  {
    label: 'Finalized',
    value: props.stats?.finalized ?? 0,
    color: 'bg-green-500',
    description: 'Successfully completed',
  },
  {
    label: 'Failed',
    value: props.stats?.failed ?? 0,
    color: 'bg-red-500',
    description: 'Failed or reverted',
  },
]);
</script>

<template>
  <div class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6">
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
        Transaction Statistics
      </h3>
      <span class="text-sm text-gray-500 dark:text-gray-400">
        Total: {{ total.toLocaleString() }}
      </span>
    </div>

    <!-- Quick Stats -->
    <div v-if="!detailed" class="grid grid-cols-2 gap-4">
      <div
        v-for="stat in statItems.slice(0, 4)"
        :key="stat.label"
        class="text-center p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg"
      >
        <div class="text-2xl font-bold text-gray-900 dark:text-white">
          {{ stat.value.toLocaleString() }}
        </div>
        <div class="text-sm text-gray-500 dark:text-gray-400">
          {{ stat.label }}
        </div>
      </div>
    </div>

    <!-- Detailed Stats -->
    <div v-else class="space-y-4">
      <!-- Progress Bar -->
      <div class="h-3 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden flex">
        <div
          v-for="stat in statItems"
          :key="stat.label"
          :class="stat.color"
          :style="{
            width: total > 0 ? `${(stat.value / total) * 100}%` : '0%',
          }"
        ></div>
      </div>

      <!-- Legend -->
      <div class="grid sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <div
          v-for="stat in statItems"
          :key="stat.label"
          class="flex items-start gap-3 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg"
        >
          <div :class="['w-3 h-3 rounded-full mt-1 flex-shrink-0', stat.color]"></div>
          <div>
            <div class="text-lg font-semibold text-gray-900 dark:text-white">
              {{ stat.value.toLocaleString() }}
            </div>
            <div class="text-sm font-medium text-gray-700 dark:text-gray-300">
              {{ stat.label }}
            </div>
            <div class="text-xs text-gray-500 dark:text-gray-400">
              {{ stat.description }}
            </div>
          </div>
        </div>
      </div>

      <!-- Success Rate -->
      <div class="mt-6 p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
        <div class="flex items-center justify-between">
          <span class="text-green-800 dark:text-green-200 font-medium">
            Success Rate
          </span>
          <span class="text-2xl font-bold text-green-600 dark:text-green-400">
            {{ successRate }}%
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
