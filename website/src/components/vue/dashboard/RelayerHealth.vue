<script setup lang="ts">
import { computed } from 'vue';
import type { StatusResponse } from '@lib/api';

interface Props {
  status: StatusResponse | null;
}

const props = defineProps<Props>();

const uptimeFormatted = computed(() => {
  if (!props.status?.uptime_seconds) return '0s';

  const seconds = props.status.uptime_seconds;
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (days > 0) {
    return `${days}d ${hours}h ${minutes}m`;
  }
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
});

const healthyChains = computed(() => {
  if (!props.status?.chain_status) return 0;
  return props.status.chain_status.filter((c) => c.healthy).length;
});

const totalChains = computed(() => props.status?.chain_status?.length ?? 0);
</script>

<template>
  <div class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6">
    <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">
      Relayer Status
    </h3>

    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <!-- Version -->
      <div class="text-center p-4 bg-primary-50 dark:bg-primary-900/20 rounded-lg">
        <div class="text-sm text-primary-600 dark:text-primary-400 font-medium mb-1">
          Version
        </div>
        <div class="text-xl font-bold text-primary-700 dark:text-primary-300">
          v{{ status?.version ?? '—' }}
        </div>
      </div>

      <!-- Uptime -->
      <div class="text-center p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
        <div class="text-sm text-green-600 dark:text-green-400 font-medium mb-1">
          Uptime
        </div>
        <div class="text-xl font-bold text-green-700 dark:text-green-300">
          {{ uptimeFormatted }}
        </div>
      </div>

      <!-- Connected Chains -->
      <div class="text-center p-4 bg-secondary-50 dark:bg-secondary-900/20 rounded-lg">
        <div class="text-sm text-secondary-600 dark:text-secondary-400 font-medium mb-1">
          Connected Chains
        </div>
        <div class="text-xl font-bold text-secondary-700 dark:text-secondary-300">
          {{ status?.connected_chains?.length ?? 0 }}
        </div>
      </div>

      <!-- Health Status -->
      <div
        :class="[
          'text-center p-4 rounded-lg',
          healthyChains === totalChains
            ? 'bg-green-50 dark:bg-green-900/20'
            : 'bg-yellow-50 dark:bg-yellow-900/20',
        ]"
      >
        <div
          :class="[
            'text-sm font-medium mb-1',
            healthyChains === totalChains
              ? 'text-green-600 dark:text-green-400'
              : 'text-yellow-600 dark:text-yellow-400',
          ]"
        >
          Chain Health
        </div>
        <div
          :class="[
            'text-xl font-bold',
            healthyChains === totalChains
              ? 'text-green-700 dark:text-green-300'
              : 'text-yellow-700 dark:text-yellow-300',
          ]"
        >
          {{ healthyChains }}/{{ totalChains }}
        </div>
      </div>
    </div>
  </div>
</template>
