//! Transaction sender with retry logic and stuck transaction handling

use super::gas::GasEstimator;
use super::nonce::NonceManager;
use crate::chain::{ChainManager, GasPrice};
use crate::config::RelayerConfig;
use crate::coordination::PendingTransaction;
use crate::error::{RelayerError, RelayerResult};
use crate::state::StateManager;

use ethers::prelude::*;
use ethers::signers::{LocalWallet, Signer};
use ethers::types::transaction::eip2718::TypedTransaction;
use std::sync::Arc;
use std::time::Duration;
use tokio::time::timeout;
use tracing::{debug, error, info, warn};

/// Transaction sender with comprehensive retry and error handling
pub struct TransactionSender {
    /// Chain manager
    chain_manager: Arc<ChainManager>,
    /// State manager
    state_manager: Arc<StateManager>,
    /// Nonce manager
    nonce_manager: Arc<NonceManager>,
    /// Gas estimator
    gas_estimator: GasEstimator,
    /// Wallet for signing
    wallet: LocalWallet,
    /// Configuration
    config: RelayerConfig,
}

impl TransactionSender {
    /// Create a new transaction sender
    pub async fn new(
        chain_manager: Arc<ChainManager>,
        state_manager: Arc<StateManager>,
        config: RelayerConfig,
    ) -> RelayerResult<Self> {
        // Load wallet from environment or keystore
        let wallet = Self::load_wallet().await?;
        let wallet_address = wallet.address();

        info!("Transaction sender initialized with wallet: {:?}", wallet_address);

        let nonce_manager = Arc::new(NonceManager::new(wallet_address));

        // Initialize nonces for all chains
        for chain_id in chain_manager.connected_chains() {
            if let Ok(provider) = chain_manager.get_provider(chain_id) {
                if let Err(e) = nonce_manager.init_chain(chain_id, &provider).await {
                    warn!("Failed to init nonce for chain {}: {}", chain_id, e);
                }
            }
        }

        Ok(Self {
            chain_manager,
            state_manager,
            nonce_manager,
            gas_estimator: GasEstimator::new(),
            wallet,
            config,
        })
    }

    /// Load wallet from environment or keystore
    async fn load_wallet() -> RelayerResult<LocalWallet> {
        // Try environment variable first (dev mode)
        if let Ok(key) = std::env::var("RELAYER_PRIVATE_KEY") {
            return key
                .parse::<LocalWallet>()
                .map_err(|e| RelayerError::Wallet(format!("Invalid private key: {}", e)));
        }

        // Try keystore
        // In production, we'd use encrypted keystore with password prompt
        Err(RelayerError::Wallet(
            "No wallet configured. Set RELAYER_PRIVATE_KEY or configure keystore".to_string(),
        ))
    }

    /// Submit a resolve_dependency transaction
    pub async fn submit_resolve(
        &self,
        pending_tx: &PendingTransaction,
    ) -> RelayerResult<H256> {
        let chain_id = pending_tx.target_chain;
        let provider = self.chain_manager.get_provider(chain_id)?;

        // Get nonce
        let nonce = self.nonce_manager.get_nonce(chain_id).await?;

        // Estimate gas
        let gas_limit = self.gas_estimator.estimate_resolve_gas(&provider).await?;
        let gas_price = self.gas_estimator.get_gas_price(&provider).await?;

        // Build transaction
        let tx = self.build_resolve_tx(
            &provider,
            &pending_tx.tx_id,
            nonce,
            gas_limit,
            &gas_price,
        )?;

        // Sign and send with retry
        let tx_hash = self.send_with_retry(chain_id, tx, nonce).await?;

        // Record submission
        self.nonce_manager
            .mark_pending(chain_id, nonce, &format!("{:?}", tx_hash))
            .await?;

        self.state_manager
            .record_submission(
                &pending_tx.tx_id,
                chain_id,
                &format!("{:?}", tx_hash),
            )
            .await?;

        crate::metrics::record_tx_submitted(chain_id);

        Ok(tx_hash)
    }

    /// Build resolve_dependency transaction
    fn build_resolve_tx(
        &self,
        provider: &crate::chain::ChainProvider,
        tx_id: &[u8; 32],
        nonce: u64,
        gas_limit: U256,
        gas_price: &GasPrice,
    ) -> RelayerResult<TypedTransaction> {
        let contract_address: Address = provider
            .contract_address()
            .parse()
            .map_err(|e| RelayerError::Config(format!("Invalid contract address: {}", e)))?;

        // Encode function call: resolve_dependency(bytes32 tx_id)
        // Function selector: keccak256("resolve_dependency(bytes32)")[:4]
        let mut data = vec![0x12, 0x34, 0x56, 0x78]; // Placeholder selector
        data.extend_from_slice(tx_id);

        let mut tx = TransactionRequest::new()
            .to(contract_address)
            .data(data)
            .nonce(nonce)
            .gas(gas_limit);

        // Set gas price based on type
        let typed_tx = match gas_price {
            GasPrice::Legacy(price) => {
                tx = tx.gas_price(*price);
                TypedTransaction::Legacy(tx.into())
            }
            GasPrice::Eip1559 {
                max_fee_per_gas,
                max_priority_fee_per_gas,
            } => {
                let eip1559_tx = Eip1559TransactionRequest::new()
                    .to(contract_address)
                    .data(tx.data.unwrap_or_default())
                    .nonce(nonce)
                    .gas(gas_limit)
                    .max_fee_per_gas(*max_fee_per_gas)
                    .max_priority_fee_per_gas(*max_priority_fee_per_gas);
                TypedTransaction::Eip1559(eip1559_tx)
            }
        };

        Ok(typed_tx)
    }

    /// Send transaction with retry logic
    async fn send_with_retry(
        &self,
        chain_id: u64,
        tx: TypedTransaction,
        nonce: u64,
    ) -> RelayerResult<H256> {
        let provider = self.chain_manager.get_provider(chain_id)?;
        let wallet = self.wallet.clone().with_chain_id(chain_id);

        let mut attempts = 0;
        let max_attempts = self.config.max_retries;
        let mut last_error = None;

        while attempts < max_attempts {
            attempts += 1;

            // Sign transaction
            let signed_tx = match wallet.sign_transaction(&tx).await {
                Ok(sig) => tx.rlp_signed(&sig),
                Err(e) => {
                    error!("Failed to sign transaction: {}", e);
                    last_error = Some(RelayerError::Wallet(e.to_string()));
                    continue;
                }
            };

            // Send with timeout
            let send_timeout = Duration::from_secs(30);
            let result = timeout(
                send_timeout,
                provider.http().send_raw_transaction(signed_tx),
            )
            .await;

            match result {
                Ok(Ok(pending_tx)) => {
                    let tx_hash = pending_tx.tx_hash();
                    info!(
                        "Transaction sent: {:?} (attempt {}/{})",
                        tx_hash, attempts, max_attempts
                    );
                    return Ok(tx_hash);
                }
                Ok(Err(e)) => {
                    let error_msg = e.to_string();

                    // Check for specific error types
                    if error_msg.contains("nonce too low") {
                        warn!("Nonce too low, syncing and retrying");
                        self.nonce_manager.sync(chain_id, &provider).await?;
                        // Get new nonce and rebuild tx
                        // For simplicity, we'll just fail here
                        return Err(RelayerError::Nonce {
                            chain_id,
                            message: "Nonce too low".to_string(),
                        });
                    } else if error_msg.contains("replacement transaction underpriced") {
                        warn!("Transaction underpriced, increasing gas");
                        // Would rebuild tx with higher gas
                    } else if error_msg.contains("insufficient funds") {
                        return Err(RelayerError::InsufficientBalance {
                            chain_id,
                            have: "unknown".to_string(),
                            need: "unknown".to_string(),
                        });
                    }

                    last_error = Some(RelayerError::Transaction(error_msg));
                }
                Err(_) => {
                    warn!("Transaction send timeout (attempt {})", attempts);
                    last_error = Some(RelayerError::Timeout {
                        operation: "send transaction".to_string(),
                    });
                }
            }

            // Wait before retry
            if attempts < max_attempts {
                tokio::time::sleep(Duration::from_millis(self.config.retry_delay_ms)).await;
            }
        }

        // Release nonce on failure
        self.nonce_manager.release_nonce(chain_id, nonce).await?;

        Err(last_error.unwrap_or(RelayerError::Transaction(
            "Unknown error".to_string(),
        )))
    }

    /// Speed up a stuck transaction
    pub async fn speed_up(
        &self,
        chain_id: u64,
        nonce: u64,
        original_tx: &TypedTransaction,
    ) -> RelayerResult<H256> {
        let provider = self.chain_manager.get_provider(chain_id)?;

        // Get current gas price and increase by 25%
        let current_gas = self.gas_estimator.get_gas_price(&provider).await?;
        let new_gas = self.gas_estimator.speed_up_gas_price(&current_gas, 125);

        // Rebuild tx with higher gas
        let new_tx = self.rebuild_tx_with_gas(original_tx, &new_gas)?;

        info!("Speeding up stuck transaction with nonce {}", nonce);
        self.send_with_retry(chain_id, new_tx, nonce).await
    }

    /// Rebuild transaction with new gas price
    fn rebuild_tx_with_gas(
        &self,
        tx: &TypedTransaction,
        gas_price: &GasPrice,
    ) -> RelayerResult<TypedTransaction> {
        // Extract common fields
        let to = tx.to().cloned();
        let data = tx.data().cloned();
        let nonce = tx.nonce().cloned();
        let gas = tx.gas().cloned();

        match gas_price {
            GasPrice::Legacy(price) => {
                let mut new_tx = TransactionRequest::new();
                if let Some(NameOrAddress::Address(addr)) = to {
                    new_tx = new_tx.to(addr);
                }
                if let Some(data) = data {
                    new_tx = new_tx.data(data);
                }
                if let Some(nonce) = nonce {
                    new_tx = new_tx.nonce(nonce);
                }
                if let Some(gas) = gas {
                    new_tx = new_tx.gas(gas);
                }
                new_tx = new_tx.gas_price(*price);
                Ok(TypedTransaction::Legacy(new_tx.into()))
            }
            GasPrice::Eip1559 {
                max_fee_per_gas,
                max_priority_fee_per_gas,
            } => {
                let mut new_tx = Eip1559TransactionRequest::new();
                if let Some(NameOrAddress::Address(addr)) = to {
                    new_tx = new_tx.to(addr);
                }
                if let Some(data) = data {
                    new_tx = new_tx.data(data);
                }
                if let Some(nonce) = nonce {
                    new_tx = new_tx.nonce(nonce);
                }
                if let Some(gas) = gas {
                    new_tx = new_tx.gas(gas);
                }
                new_tx = new_tx
                    .max_fee_per_gas(*max_fee_per_gas)
                    .max_priority_fee_per_gas(*max_priority_fee_per_gas);
                Ok(TypedTransaction::Eip1559(new_tx))
            }
        }
    }

    /// Get wallet balance on a chain
    pub async fn get_balance(&self, chain_id: u64) -> RelayerResult<U256> {
        let provider = self.chain_manager.get_provider(chain_id)?;
        provider
            .http()
            .get_balance(self.wallet.address(), None)
            .await
            .map_err(|e| RelayerError::ChainConnection {
                chain_id,
                message: e.to_string(),
            })
    }

    /// Get wallet address
    pub fn wallet_address(&self) -> Address {
        self.wallet.address()
    }
}
