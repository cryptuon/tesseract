//! Configuration management for the Tesseract Relayer
//!
//! Loads configuration from TOML files with environment variable substitution.

use anyhow::{Context, Result};
use serde::Deserialize;
use std::collections::HashMap;
use std::env;
use std::path::PathBuf;

/// Root configuration structure
#[derive(Debug, Clone, Deserialize)]
pub struct Settings {
    pub relayer: RelayerConfig,
    pub database: DatabaseConfig,
    pub api: ApiConfig,
    pub metrics: MetricsConfig,
    pub chains: HashMap<String, ChainConfig>,
    pub wallet: WalletConfig,
    pub alerts: AlertsConfig,
}

#[derive(Debug, Clone, Deserialize)]
pub struct RelayerConfig {
    pub instance_id: String,
    pub poll_interval_ms: u64,
    pub max_concurrent_txs: usize,
    pub max_retries: u32,
    pub retry_delay_ms: u64,
    pub health_check_interval_secs: u64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct DatabaseConfig {
    pub url: String,
    pub max_connections: u32,
    pub min_connections: u32,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ApiConfig {
    pub host: String,
    pub port: u16,
}

#[derive(Debug, Clone, Deserialize)]
pub struct MetricsConfig {
    pub enabled: bool,
    pub port: u16,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ChainConfig {
    pub chain_id: u64,
    pub name: String,
    pub rpc_urls: Vec<String>,
    pub ws_url: Option<String>,
    pub contract_address: String,
    pub coordinator_address: String,
    pub confirmation_blocks: u64,
    pub gas_price_strategy: GasPriceStrategy,
    pub max_gas_price_gwei: u64,
    pub enabled: bool,
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum GasPriceStrategy {
    Legacy,
    Eip1559,
    Arbitrum,
    Optimism,
}

#[derive(Debug, Clone, Deserialize)]
pub struct WalletConfig {
    pub keystore_path: Option<String>,
    pub private_key_env: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct AlertsConfig {
    pub min_balance_eth: f64,
    pub slack_webhook_url: Option<String>,
    pub pagerduty_key: Option<String>,
}

impl Settings {
    /// Load settings from configuration files
    pub fn load() -> Result<Self> {
        let config_path = env::var("TESSERACT_CONFIG")
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from("config/default.toml"));

        let config_str = std::fs::read_to_string(&config_path)
            .with_context(|| format!("Failed to read config file: {:?}", config_path))?;

        // Substitute environment variables
        let config_str = substitute_env_vars(&config_str);

        let settings: Settings = toml::from_str(&config_str)
            .with_context(|| "Failed to parse configuration")?;

        settings.validate()?;

        Ok(settings)
    }

    /// Load settings for a specific environment
    pub fn load_env(env_name: &str) -> Result<Self> {
        let config_path = PathBuf::from(format!("config/{}.toml", env_name));
        env::set_var("TESSERACT_CONFIG", config_path.to_str().unwrap());
        Self::load()
    }

    /// Validate configuration
    fn validate(&self) -> Result<()> {
        // At least one chain must be enabled
        if self.enabled_chains().is_empty() {
            anyhow::bail!("At least one chain must be enabled");
        }

        // Validate chain configurations
        for (name, chain) in &self.chains {
            if chain.enabled {
                if chain.rpc_urls.is_empty() {
                    anyhow::bail!("Chain {} has no RPC URLs configured", name);
                }
                if chain.contract_address.is_empty() {
                    tracing::warn!("Chain {} has no contract address - will skip", name);
                }
            }
        }

        Ok(())
    }

    /// Get list of enabled chains
    pub fn enabled_chains(&self) -> Vec<(&String, &ChainConfig)> {
        self.chains
            .iter()
            .filter(|(_, c)| c.enabled)
            .collect()
    }

    /// Get chain config by chain ID
    pub fn get_chain_by_id(&self, chain_id: u64) -> Option<&ChainConfig> {
        self.chains.values().find(|c| c.chain_id == chain_id)
    }
}

/// Substitute environment variables in the format ${VAR_NAME}
fn substitute_env_vars(input: &str) -> String {
    let mut result = input.to_string();
    let re = regex::Regex::new(r"\$\{([A-Z_][A-Z0-9_]*)\}").unwrap();

    for cap in re.captures_iter(input) {
        let var_name = &cap[1];
        let var_value = env::var(var_name).unwrap_or_default();
        result = result.replace(&cap[0], &var_value);
    }

    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_env_var_substitution() {
        env::set_var("TEST_VAR", "test_value");
        let input = "url = \"https://api.example.com/${TEST_VAR}/endpoint\"";
        let result = substitute_env_vars(input);
        assert_eq!(result, "url = \"https://api.example.com/test_value/endpoint\"");
    }
}
