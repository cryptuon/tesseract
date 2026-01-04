-- Tesseract Relayer Database Schema
-- Initial migration

-- Chain checkpoints for restart recovery
CREATE TABLE IF NOT EXISTS chain_checkpoints (
    chain_id BIGINT PRIMARY KEY,
    block_number BIGINT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Pending cross-chain transactions
CREATE TABLE IF NOT EXISTS pending_transactions (
    tx_id BYTEA PRIMARY KEY,
    origin_chain BIGINT NOT NULL,
    target_chain BIGINT NOT NULL,
    dependency_id BYTEA,
    swap_group_id BYTEA,
    state VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pending_state ON pending_transactions (state);
CREATE INDEX idx_pending_origin ON pending_transactions (origin_chain);
CREATE INDEX idx_pending_target ON pending_transactions (target_chain);
CREATE INDEX idx_pending_swap_group ON pending_transactions (swap_group_id) WHERE swap_group_id IS NOT NULL;

-- Contract events for auditing and debugging
CREATE TABLE IF NOT EXISTS contract_events (
    id BIGSERIAL PRIMARY KEY,
    chain_id BIGINT NOT NULL,
    block_number BIGINT NOT NULL,
    tx_hash VARCHAR(66) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_events_chain_block ON contract_events (chain_id, block_number);
CREATE INDEX idx_events_type ON contract_events (event_type);
CREATE INDEX idx_events_created ON contract_events (created_at);

-- Transaction submissions tracking
CREATE TABLE IF NOT EXISTS tx_submissions (
    id BIGSERIAL PRIMARY KEY,
    tx_id BYTEA NOT NULL,
    chain_id BIGINT NOT NULL,
    ethereum_tx_hash VARCHAR(66) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    gas_price BIGINT,
    gas_used BIGINT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE INDEX idx_submissions_tx_id ON tx_submissions (tx_id);
CREATE INDEX idx_submissions_status ON tx_submissions (status);
CREATE INDEX idx_submissions_chain ON tx_submissions (chain_id);
CREATE INDEX idx_submissions_eth_hash ON tx_submissions (ethereum_tx_hash);

-- Swap orders from AtomicSwapCoordinator
CREATE TABLE IF NOT EXISTS swap_orders (
    order_id BYTEA PRIMARY KEY,
    maker_address VARCHAR(42) NOT NULL,
    taker_address VARCHAR(42),
    offer_chain BIGINT NOT NULL,
    offer_token VARCHAR(42) NOT NULL,
    offer_amount NUMERIC(78, 0) NOT NULL,
    want_chain BIGINT NOT NULL,
    want_token VARCHAR(42) NOT NULL,
    want_amount NUMERIC(78, 0) NOT NULL,
    min_receive_amount NUMERIC(78, 0) NOT NULL,
    deadline TIMESTAMPTZ NOT NULL,
    state VARCHAR(20) NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orders_state ON swap_orders (state);
CREATE INDEX idx_orders_maker ON swap_orders (maker_address);
CREATE INDEX idx_orders_deadline ON swap_orders (deadline);

-- Swap fills
CREATE TABLE IF NOT EXISTS swap_fills (
    fill_id BYTEA PRIMARY KEY,
    order_id BYTEA NOT NULL REFERENCES swap_orders(order_id),
    taker_address VARCHAR(42) NOT NULL,
    offer_amount_filled NUMERIC(78, 0) NOT NULL,
    want_amount_filled NUMERIC(78, 0) NOT NULL,
    chain_id BIGINT NOT NULL,
    tx_hash VARCHAR(66) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_fills_order ON swap_fills (order_id);
CREATE INDEX idx_fills_taker ON swap_fills (taker_address);

-- Relayer metrics (for historical analysis)
CREATE TABLE IF NOT EXISTS relayer_metrics (
    id BIGSERIAL PRIMARY KEY,
    chain_id BIGINT NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DOUBLE PRECISION NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_metrics_chain_name ON relayer_metrics (chain_id, metric_name);
CREATE INDEX idx_metrics_recorded ON relayer_metrics (recorded_at);

-- Partitioning for events (optional, for high-volume production)
-- Consider partitioning contract_events by created_at for better performance
