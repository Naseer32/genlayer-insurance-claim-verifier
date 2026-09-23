# GenLayer Insurance Claim Verifier

A parametric insurance intelligent contract on GenLayer. Insurers fund policy pools with real GEN escrow, buyers pay a premium, and claims are adjudicated by AI validators that read the policy terms and the evidence URLs, reaching consensus on the decision.

## Deployment (GenLayer Studio)

- Contract: `0x083041CAE1959B912eA3af5e336659E26CB38207`
- Explorer: https://explorer-studio.genlayer.com/address/0x083041CAE1959B912eA3af5e336659E26CB38207
- Source: `contracts/insurance_claim_verifier.py`

## How it works

1. `create_policy_pool(name, terms_text, premium_wei, max_payout_wei)` (payable): an insurer opens a pool and funds it with a GEN escrow.
2. `buy_policy(pool_id)` (payable): a buyer pays exactly the premium and becomes insured under that pool.
3. `submit_claim(pool_id, description, evidence_urls)`: an insured buyer files a claim with one or more evidence URLs (separated by `|`). A deterministic evidence-reuse guard rejects reused evidence before any AI runs.
4. `resolve_claim(claim_id)`: anyone can trigger it. AI validators read the policy terms and the evidence and reach consensus on `approved` or `denied` plus a payout fraction. On approval the payout is sent from the pool escrow to the claimant.
5. Views: `get_pools`, `get_claims`, `get_pool`, `get_claim`.

## Live test results (GenLayer Studio)

Test pool `pool_0` "Flood Cover Basic": premium 2 GEN, max payout 3 GEN, terms require clear evidence of flooding damage at the insured property from an official or news source.

| Step | Tx hash |
|---|---|
| Deploy | 0xee607c882ef64f0df5a124c384f13aff4a015c9cfcad2d11a5c63989c775623b |
| create_policy_pool | 0x4f32e6c454d1641a5907fc02ba2903d4a7516b24b28acbc865a900d3b6778ce0 |
| buy_policy | 0x3a48c38c3bce1369ff3584da0cb76f3854b384b5361f0b47c8f5e7c4bff7faf5 |
| submit_claim (claim_1) | 0xaafe35a76371e6e23ee3e5dccdf3a03f0ac85df76ea8d4e8d74c5f282d992b99 |
| resolve_claim (claim_1, DENIED) | 0x3d579569689e1e22b53db9a33c9b1467ecb86e41cc6305b83ffb596f6b79433c |
| submit_claim (claim_2) | 0x6accef44ccfbc0f46f5496f260f45219a1b0de15219dad6270d5b6ac8ca837ba |
| resolve_claim (claim_2, APPROVED) | 0x6d2e5dfee0f71c7551b07499624e4bfcd45ef99cd47a1aa01318db6bd3f7d40b |

- claim_1: the evidence showed general flooding in Pakistan but no damage at the insured property, so validators denied it (payout 0).
- claim_2: the evidence named the insured property directly, validators approved 100% and 3 GEN was paid out. Pool balance went from 7 GEN to 4 GEN.

## Evidence note

The evidence used for claim_2 (`evidence/nowshera_flood_report.txt`) is a test fixture written for this demo, not a real news article. The claim on chain references the raw file URL in the `Naseer32/genlayer-bug-bounty` repository.

## Known limitations and next steps

This is a hackathon prototype. The deployed contract intentionally keeps the logic simple, and these are the known gaps I would close in a v2:

1. **Repeat claims per policy.** A policyholder can file several claims under one policy, each with new evidence, until the pool is drained. The evidence-reuse guard only blocks reusing the same URL. Fix: mark the policy as claimed once a claim is approved.
2. **Claimant chooses the evidence.** Nothing stops a claimant from hosting their own "news article". Fix: per-pool `trusted_domains` allowlist, plus a prompt instruction that fetched evidence is untrusted data and must never be followed as instructions.
3. **No way for the insurer to withdraw.** There is no `close_pool` or `withdraw`, so the escrow stays locked. `POOL_CLOSED` exists but is not used yet.
4. **No waiting period or incident date.** A buyer can purchase a policy and claim immediately. Fix: add a coverage start delay and an incident date check against the evidence.

The demo evidence for claim_2 is a self-written test fixture, which is exactly the weakness described in point 2.
