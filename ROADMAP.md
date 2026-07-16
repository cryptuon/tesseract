# Tesseract Roadmap

**Vision:** Tesseract is the atomic-execution layer for the cross-chain agent economy. As autonomous agents, intent solvers, and DeFi protocols increasingly operate across many Ethereum L2s at once, they need **atomic composability** — the guarantee that a multi-rollup action either completes everywhere or refunds everywhere. Bridges cannot provide this; they introduce custodial locks, wrapped IOUs, and mid-flight failure. Tesseract provides all-or-nothing, intent-style cross-rollup settlement enforced on-chain by Vyper contracts, with commit-reveal MEV protection and a Rust relayer that submits but never authorizes. The roadmap below takes Tesseract from its current production-leaning state to a trust-minimized, agent-facing protocol running on mainnet L2s.

This document is grounded in the mechanics that already exist in the repo: a three-phase Buffer → Resolve → Execute protocol, atomic swap groups bound by a shared `swap_group_id`, a configurable coordination window (5–300s, default 30s), a ≥2-block reveal→resolve delay, and a WebSocket + HTTP-failover Rust relayer with Prometheus metrics.

---

## Near-term milestones (next 1–2 quarters)

- **Third-party security audit** of the seven Vyper contracts *and* the Rust relayer coordination logic. This is the primary gate before any mainnet value. (See scope in [Cheapest path to production](#cheapest-path-to-production).)
- **Testnet hardening on one cheap L2 pair**: full Buffer → Resolve → Execute lifecycle on **Base Sepolia ↔ OP Sepolia**, including failure/refund and timeout paths, under sustained load.
- **Relayer liveness & redundancy**: run ≥2 relayer instances across regions with WebSocket + HTTP failover (already supported), automatic nonce-gap recovery, and Prometheus + alerting wired to on-call.
- **Coordination-window tuning**: document the safe minimum window per L2 pair given the ≥2-block resolution delay and each chain's block time.
- **Reference agent/intent example**: a documented end-to-end example of an autonomous agent submitting a cross-rollup intent and receiving an atomic outcome or refund.

## Mid-term milestones

- **Staged mainnet launch on Base ↔ Optimism** with conservative per-swap and per-group value caps, lifted as confidence accrues.
- **Add Arbitrum** as the third supported mainnet chain, enabling three-way atomic swap groups (A ↔ B ↔ C).
- **Agent/intent-facing SDK**: a typed client (Rust + TypeScript) that lets agents and solvers express intents as swap groups without hand-rolling commit-reveal.
- **Relayer registry economics**: TESS-bonded relayers with slashing for missed resolutions; make the relayer set permissionless-to-join.
- **Gas & latency benchmarking suite**: publish real per-swap-group cost and settlement-latency numbers per L2 pair.

## Long-term milestones

- **Decentralized relayer set** with competitive resolution and censorship-resistance guarantees ("any relayer can resolve any swap").
- **Broader L2 coverage**: additional OP-Stack chains, zk-rollups, and alignment with emerging shared-sequencing / interop standards (e.g. OP Superchain interop) where it strengthens atomicity without adding trust.
- **On-chain governance maturity** via `TesseractGovernor` on each rollup: parameter changes, relayer policy, and treasury flow through transparent proposals.
- **Formal verification** of the core buffer/resolution state machine against the *Universal Atomic Composability* model.

---

## Cheapest path to production

Tesseract is Vyper contracts + a Rust relayer for Ethereum L2s. The cheapest *viable* path to a real mainnet launch is to **avoid L1 entirely for the swap legs and launch on a single low-fee OP-Stack L2 pair first.** Concretely:

### 1. Launch pair: Base ↔ Optimism (Arbitrum as the third chain)

Launch on **Base ↔ Optimism** as the first mainnet pair. Rationale:

- **Both are OP-Stack chains** with ~2s block times, shared tooling, and Superchain alignment — one integration profile, not two.
- **Sub-cent typical L2 gas.** The README gas table shows Tesseract operations in the **~80k–200k gas** range (`buffer_transaction` ~120k, `buffer_transaction_with_commitment` ~150k, `reveal_transaction` ~80k, `resolve_dependency` ~100k, `fill_swap_order` ~200k). On OP-Stack L2s at typical sub-gwei effective execution gas prices, each of these operations costs **fractions of a cent** in L2 execution gas — versus **dollars** for the same ops on Ethereum L1. (L1 data-availability fees dominate OP-Stack cost, but Tesseract's ≤512-byte payloads keep calldata small.)
- **Arbitrum is the natural third chain** once the Base ↔ Optimism pair is proven, enabling three-way atomic groups without a second toolchain.

**Do not run swap legs on L1 mainnet.** At L1 gas prices a single atomic swap group (multiple ops per leg × multiple legs) can cost tens of dollars; the same group on Base ↔ Optimism costs a few cents. L1 is only relevant as the settlement/DA root the L2s already post to.

### 2. Contract + relayer audit scope

- **Contracts (Vyper, 7):** focus on `TesseractBuffer` (commit-reveal, swap-group atomicity, refund paths, resolution delay), `AtomicSwapCoordinator` (order book, partial fills, slippage), and access control (`BUFFER_ROLE` / `RESOLVE_ROLE` / `ADMIN_ROLE`, emergency admin, circuit breaker). Verify: no partial-resolution state is reachable; refunds are always claimable after deadline; the ≥2-block delay cannot be bypassed.
- **Relayer (Rust):** audit the coordination engine, nonce management, and finality tracking — specifically that the relayer cannot cause funds to move outside contract-enforced resolution, and that stuck/duplicate submissions cannot double-resolve or block refunds.

### 3. Testnet → mainnet plan (one cheap pair first)

1. **Base Sepolia ↔ OP Sepolia**: deploy all contracts, run the full lifecycle including timeout/refund and failure injection under sustained load; publish results.
2. **Base ↔ OP mainnet, capped**: launch with strict per-swap and per-group value caps and a short allow-list of assets. Keep the emergency pause and circuit breaker live.
3. **Lift caps in stages** as clean settlement volume accrues, then **add Arbitrum** as the third chain.

### 4. Relayer liveness / redundancy

- Run **≥2 relayer instances across regions** (already supported via WebSocket monitoring + HTTP failover). No single relayer is a liveness dependency — any relayer can submit resolution.
- **Health/liveness monitoring** with Prometheus metrics (already exported) + Grafana + on-call alerting; page on missed resolutions, RPC failover events, and rising refund rates.
- **Automatic nonce-gap recovery** and stuck-transaction handling enabled on every instance.
- **Multi-RPC failover** per chain so a single provider outage does not stall coordination.

### 5. Coordination-window tuning

- The **default 30s window is comfortable on OP-Stack**: at ~2s block time that is ~15 blocks of headroom, well above the ≥2-block reveal→resolve delay.
- Tune the window **per pair** and document the **safe minimum**: it must exceed (reveal delay + resolution delay + worst-case relayer submission latency + a finality margin) for the slowest chain in the group. For Base ↔ Optimism a 15–30s window is reasonable; do not push below the point where a congested block can push resolution past the deadline and force needless refunds.

### 6. MEV / commit-reveal parameters

- **Keep the ≥2-block reveal→resolve delay.** It provides both flash-loan resistance (an attack cannot span two blocks) and MEV protection (the payload is opaque until block ordering is already settled).
- **Document the reveal-window trade-off:** a longer gap between commit and reveal hides intent longer but adds latency; a shorter gap is faster but narrows the safety margin. The chosen window (5–300s) bounds how long a committed-but-unrevealed leg can sit before it must refund.

### 7. Gas-cost budgeting (estimates)

**Per swap-group execution gas (back-of-envelope, one give-leg + one take-leg):**

| Operation (per leg)                     | Gas (README) |
| --------------------------------------- | ------------ |
| `buffer_transaction_with_commitment`    | ~150,000     |
| `reveal_transaction`                    | ~80,000      |
| `resolve_dependency`                    | ~100,000     |
| **Per leg subtotal**                    | **~330,000** |
| **Two-leg group (give + take)**         | **~660,000** |

At a **sub-gwei effective execution gas price** typical of OP-Stack L2s, ~660k gas of execution is on the order of **a fraction of a cent to a few cents per group** in L2 execution gas (exact figure moves with L2 gas price and, more importantly, with L1 DA fees at post time — but Tesseract's ≤512-byte payloads keep calldata cost small). *These are order-of-magnitude estimates; measure real numbers on testnet before publishing.*

**Monthly relayer infrastructure budget (estimate):**

| Item                                    | Est. monthly |
| --------------------------------------- | ------------ |
| 2× small cloud instances (redundant)    | ~$30–80      |
| Managed PostgreSQL (state persistence)  | ~$15–50      |
| RPC access (2 chains, WS + HTTP, failover) | ~$0–250 (free tiers → paid as volume grows) |
| Monitoring (Prometheus/Grafana self-hosted or free tier) | ~$0–30 |
| **Total**                               | **~$45–410/mo** |

The dominant variable cost is RPC as volume scales; execution gas per group is negligible on OP-Stack. *Estimates — validate against your provider quotes.*

---

**Bottom line:** launch on **Base ↔ Optimism** after a contract + relayer audit, stage from testnet to capped mainnet, run ≥2 redundant relayers with monitoring, keep the ≥2-block delay and a tuned 15–30s window, and expect **cents-per-group execution cost** with a **low-tens-to-low-hundreds of dollars/month** infra footprint. Add Arbitrum as the third chain once the pair is proven.
