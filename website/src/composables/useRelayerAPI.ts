import { ref, onMounted, onUnmounted } from 'vue';
import type { Ref } from 'vue';
import api, { type StatsResponse, type StatusResponse, type ChainHealth } from '../lib/api';

interface UseRelayerAPIOptions {
  pollInterval?: number;
  autoStart?: boolean;
}

interface UseRelayerAPIReturn {
  stats: Ref<StatsResponse | null>;
  status: Ref<StatusResponse | null>;
  chainHealth: Ref<ChainHealth[]>;
  loading: Ref<boolean>;
  error: Ref<string | null>;
  isConnected: Ref<boolean>;
  refresh: () => Promise<void>;
  startPolling: () => void;
  stopPolling: () => void;
}

export function useRelayerAPI(options: UseRelayerAPIOptions = {}): UseRelayerAPIReturn {
  const { pollInterval = 15000, autoStart = true } = options;

  const stats = ref<StatsResponse | null>(null);
  const status = ref<StatusResponse | null>(null);
  const chainHealth = ref<ChainHealth[]>([]);
  const loading = ref(true);
  const error = ref<string | null>(null);
  const isConnected = ref(false);

  let intervalId: ReturnType<typeof setInterval> | null = null;

  async function fetchData() {
    try {
      const [statsData, statusData] = await Promise.all([
        api.stats(),
        api.status(),
      ]);

      stats.value = statsData;
      status.value = statusData;
      chainHealth.value = statusData.chain_status;
      isConnected.value = true;
      error.value = null;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to connect to relayer';
      isConnected.value = false;
    } finally {
      loading.value = false;
    }
  }

  function startPolling() {
    if (intervalId) return;
    fetchData();
    intervalId = setInterval(fetchData, pollInterval);
  }

  function stopPolling() {
    if (intervalId) {
      clearInterval(intervalId);
      intervalId = null;
    }
  }

  async function refresh() {
    loading.value = true;
    await fetchData();
  }

  onMounted(() => {
    if (autoStart) {
      startPolling();
    }
  });

  onUnmounted(() => {
    stopPolling();
  });

  return {
    stats,
    status,
    chainHealth,
    loading,
    error,
    isConnected,
    refresh,
    startPolling,
    stopPolling,
  };
}

// Separate composable for chain status with faster polling
export function useChainStatus(pollInterval = 10000) {
  const chains = ref<ChainHealth[]>([]);
  const loading = ref(true);
  const error = ref<string | null>(null);

  let intervalId: ReturnType<typeof setInterval> | null = null;

  async function fetchStatus() {
    try {
      const data = await api.ready();
      chains.value = data.details;
      error.value = null;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch chain status';
    } finally {
      loading.value = false;
    }
  }

  onMounted(() => {
    fetchStatus();
    intervalId = setInterval(fetchStatus, pollInterval);
  });

  onUnmounted(() => {
    if (intervalId) {
      clearInterval(intervalId);
    }
  });

  return { chains, loading, error, refresh: fetchStatus };
}

// Separate composable for transaction stats
export function useTransactionStats(pollInterval = 15000) {
  const stats = ref<StatsResponse | null>(null);
  const loading = ref(true);
  const error = ref<string | null>(null);
  const total = ref(0);

  let intervalId: ReturnType<typeof setInterval> | null = null;

  async function fetchStats() {
    try {
      const data = await api.stats();
      stats.value = data;
      total.value = data.buffered + data.ready + data.submitted + data.finalized + data.failed;
      error.value = null;
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Failed to fetch stats';
    } finally {
      loading.value = false;
    }
  }

  onMounted(() => {
    fetchStats();
    intervalId = setInterval(fetchStats, pollInterval);
  });

  onUnmounted(() => {
    if (intervalId) {
      clearInterval(intervalId);
    }
  });

  return { stats, total, loading, error, refresh: fetchStats };
}
