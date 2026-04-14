<script setup lang="ts">
import { ref, computed } from 'vue';
import ChainStatusCard from './ChainStatusCard.vue';
import TransactionStats from './TransactionStats.vue';
import RelayerHealth from './RelayerHealth.vue';
import { useRelayerAPI } from '../../../composables/useRelayerAPI';

const { status, stats, chainHealth, loading, error, isConnected } = useRelayerAPI({
  pollInterval: 10000,
});

const activeTab = ref<'overview' | 'chains' | 'transactions'>('overview');

// API URL for display (can't use import.meta directly in template)
const apiUrl = computed(() => {
  // @ts-ignore
  return import.meta.env?.PUBLIC_API_URL || 'http://localhost:8080';
});
</script>

<template>
  <div class="space-y-6">
    <!-- Connection Status Banner -->
    <div
      v-if="!loading"
      :class="[
        'rounded-lg p-4 flex items-center gap-3',
        isConnected
          ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800'
          : 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800',
      ]"
    >
      <div
        :class="[
          'w-3 h-3 rounded-full',
          isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500',
        ]"
      ></div>
      <div>
        <span
          :class="[
            'font-medium',
            isConnected
              ? 'text-green-800 dark:text-green-200'
              : 'text-red-800 dark:text-red-200',
          ]"
        >
          {{ isConnected ? 'Connected to Relayer' : 'Disconnected' }}
        </span>
        <span
          v-if="status?.version"
          class="ml-2 text-sm text-green-600 dark:text-green-400"
        >
          v{{ status.version }}
        </span>
      </div>
      <div
        v-if="error"
        class="ml-auto text-sm text-red-600 dark:text-red-400"
      >
        {{ error }}
      </div>
    </div>

    <!-- Loading State -->
    <div
      v-if="loading"
      class="flex items-center justify-center py-12"
    >
      <div class="flex items-center gap-3 text-gray-500 dark:text-gray-400">
        <svg
          class="animate-spin h-6 w-6"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            class="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            stroke-width="4"
          ></circle>
          <path
            class="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          ></path>
        </svg>
        <span>Connecting to relayer...</span>
      </div>
    </div>

    <!-- Dashboard Content -->
    <template v-else-if="isConnected">
      <!-- Tab Navigation -->
      <div class="border-b border-gray-200 dark:border-gray-700">
        <nav class="flex gap-4" aria-label="Dashboard tabs">
          <button
            v-for="tab in [
              { id: 'overview', label: 'Overview' },
              { id: 'chains', label: 'Chain Status' },
              { id: 'transactions', label: 'Transactions' },
            ]"
            :key="tab.id"
            :class="[
              'pb-3 px-1 text-sm font-medium border-b-2 transition-colors',
              activeTab === tab.id
                ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300',
            ]"
            @click="activeTab = tab.id as typeof activeTab"
          >
            {{ tab.label }}
          </button>
        </nav>
      </div>

      <!-- Overview Tab -->
      <div v-if="activeTab === 'overview'" class="space-y-6">
        <!-- Relayer Health -->
        <RelayerHealth :status="status" />

        <!-- Stats Grid -->
        <div class="grid md:grid-cols-2 gap-6">
          <TransactionStats :stats="stats" />

          <!-- Chain Status Summary -->
          <div class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6">
            <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Connected Chains
            </h3>
            <div class="space-y-3">
              <div
                v-for="chain in chainHealth"
                :key="chain.chain_id"
                class="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-700 last:border-0"
              >
                <span class="text-gray-700 dark:text-gray-300">
                  Chain {{ chain.chain_id }}
                </span>
                <span
                  :class="[
                    'inline-flex items-center gap-1.5 text-sm',
                    chain.healthy
                      ? 'text-green-600 dark:text-green-400'
                      : 'text-red-600 dark:text-red-400',
                  ]"
                >
                  <span
                    :class="[
                      'w-2 h-2 rounded-full',
                      chain.healthy ? 'bg-green-500' : 'bg-red-500',
                    ]"
                  ></span>
                  {{ chain.healthy ? 'Healthy' : 'Unhealthy' }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Chains Tab -->
      <div v-if="activeTab === 'chains'" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <ChainStatusCard
          v-for="chain in chainHealth"
          :key="chain.chain_id"
          :chain="chain"
        />
      </div>

      <!-- Transactions Tab -->
      <div v-if="activeTab === 'transactions'">
        <TransactionStats :stats="stats" :detailed="true" />
      </div>
    </template>

    <!-- Disconnected State -->
    <div
      v-else-if="!loading && !isConnected"
      class="text-center py-12"
    >
      <div class="w-16 h-16 mx-auto mb-4 bg-red-100 dark:bg-red-900/30 rounded-full flex items-center justify-center">
        <svg
          class="w-8 h-8 text-red-500"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
          />
        </svg>
      </div>
      <h3 class="text-lg font-medium text-gray-900 dark:text-white mb-2">
        Unable to Connect
      </h3>
      <p class="text-gray-500 dark:text-gray-400 mb-4">
        Could not connect to the Tesseract relayer. Please check your connection settings.
      </p>
      <p class="text-sm text-gray-400 dark:text-gray-500">
        API endpoint: {{ apiUrl }}
      </p>
    </div>
  </div>
</template>
