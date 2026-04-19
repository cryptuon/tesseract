<script setup lang="ts">
import { computed } from 'vue';
import type { ChainHealth } from '@lib/api';
import { getNetworkByChainId } from '@lib/constants';

interface Props {
  chain: ChainHealth;
}

const props = defineProps<Props>();

const network = computed(() => getNetworkByChainId(props.chain.chain_id));

const networkName = computed(() => network.value?.name || `Chain ${props.chain.chain_id}`);
const networkColor = computed(() => network.value?.iconColor || '#6366f1');
const networkShortName = computed(() => network.value?.shortName || 'UNK');
</script>

<template>
  <div
    :class="[
      'bg-white dark:bg-gray-800 border rounded-xl p-6 transition-colors',
      chain.healthy
        ? 'border-gray-200 dark:border-gray-700 hover:border-green-300 dark:hover:border-green-700'
        : 'border-red-200 dark:border-red-800',
    ]"
  >
    <div class="flex items-start justify-between mb-4">
      <!-- Network Icon -->
      <div
        class="w-12 h-12 rounded-xl flex items-center justify-center text-white font-bold"
        :style="{ backgroundColor: networkColor }"
      >
        {{ networkShortName.slice(0, 3) }}
      </div>

      <!-- Status Badge -->
      <span
        :class="[
          'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium',
          chain.healthy
            ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300'
            : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300',
        ]"
      >
        <span
          :class="[
            'w-1.5 h-1.5 rounded-full',
            chain.healthy ? 'bg-green-500 animate-pulse' : 'bg-red-500',
          ]"
        ></span>
        {{ chain.healthy ? 'Healthy' : 'Unhealthy' }}
      </span>
    </div>

    <!-- Network Info -->
    <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-1">
      {{ networkName }}
    </h3>

    <div class="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
      <span>Chain ID: {{ chain.chain_id }}</span>
      <span v-if="network?.isTestnet" class="px-1.5 py-0.5 bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300 rounded text-xs">
        Testnet
      </span>
    </div>

    <!-- Explorer Link -->
    <a
      v-if="network?.explorerUrl"
      :href="network.explorerUrl"
      target="_blank"
      rel="noopener noreferrer"
      class="mt-4 inline-flex items-center gap-1 text-sm text-primary-600 dark:text-primary-400 hover:underline"
    >
      View Explorer
      <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
      </svg>
    </a>
  </div>
</template>
