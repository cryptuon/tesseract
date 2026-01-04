//! Gas estimation and optimization for different chain types

use crate::chain::{ChainProvider, GasPrice};
use crate::config::GasPriceStrategy;
use crate::error::{RelayerError, RelayerResult};

use ethers::types::U256;
use tracing::debug;

/// Gas estimator for transactions
pub struct GasEstimator {
    /// Buffer percentage for gas limit (e.g., 20 = 20% buffer)
    gas_limit_buffer_percent: u64,
    /// Buffer percentage for gas price
    gas_price_buffer_percent: u64,
}

impl GasEstimator {
    /// Create a new gas estimator
    pub fn new() -> Self {
        Self {
            gas_limit_buffer_percent: 20,
            gas_price_buffer_percent: 10,
        }
    }

    /// Estimate gas for a resolve_dependency call
    pub async fn estimate_resolve_gas(&self, provider: &ChainProvider) -> RelayerResult<U256> {
        // Base gas for resolve_dependency is around 50-100k
        // We add a buffer for safety
        let base_gas = U256::from(100_000);
        let buffer = base_gas * self.gas_limit_buffer_percent / 100;
        Ok(base_gas + buffer)
    }

    /// Get optimized gas price for a chain
    pub async fn get_gas_price(&self, provider: &ChainProvider) -> RelayerResult<GasPrice> {
        let gas_price = provider.get_gas_price().await?;

        // Add buffer to gas price
        let buffered = match gas_price {
            GasPrice::Legacy(price) => {
                let buffer = price * self.gas_price_buffer_percent / 100;
                GasPrice::Legacy(price + buffer)
            }
            GasPrice::Eip1559 {
                max_fee_per_gas,
                max_priority_fee_per_gas,
            } => {
                let fee_buffer = max_fee_per_gas * self.gas_price_buffer_percent / 100;
                let priority_buffer =
                    max_priority_fee_per_gas * self.gas_price_buffer_percent / 100;
                GasPrice::Eip1559 {
                    max_fee_per_gas: max_fee_per_gas + fee_buffer,
                    max_priority_fee_per_gas: max_priority_fee_per_gas + priority_buffer,
                }
            }
        };

        debug!("Gas price for chain {}: {:?}", provider.chain_id(), buffered);
        Ok(buffered)
    }

    /// Calculate speed-up gas price for stuck transaction
    pub fn speed_up_gas_price(&self, current: &GasPrice, factor: u64) -> GasPrice {
        match current {
            GasPrice::Legacy(price) => {
                GasPrice::Legacy(*price * factor / 100)
            }
            GasPrice::Eip1559 {
                max_fee_per_gas,
                max_priority_fee_per_gas,
            } => GasPrice::Eip1559 {
                max_fee_per_gas: *max_fee_per_gas * factor / 100,
                max_priority_fee_per_gas: *max_priority_fee_per_gas * factor / 100,
            },
        }
    }

    /// Calculate total cost in wei
    pub fn calculate_cost(gas_limit: U256, gas_price: &GasPrice) -> U256 {
        match gas_price {
            GasPrice::Legacy(price) => gas_limit * *price,
            GasPrice::Eip1559 { max_fee_per_gas, .. } => gas_limit * *max_fee_per_gas,
        }
    }
}

impl Default for GasEstimator {
    fn default() -> Self {
        Self::new()
    }
}
