# GenLayer Insurance Claim Verifier

A parametric insurance intelligent contract on GenLayer. Insurers fund policy pools with real GEN escrow, buyers pay a premium, and claims are adjudicated by AI validators that read the policy terms and the evidence URLs, reaching consensus on the decision.

## Deployment (GenLayer Studio)

- Contract: `0xEA9ed2e60dE54Ec0550840e11dAb36368DFc8793`
- Explorer: https://explorer-studio.genlayer.com/address/0xEA9ed2e60dE54Ec0550840e11dAb36368DFc8793
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
| Deploy (v2, deterministic payout) | 0xEA9ed2e60dE54Ec0550840e11dAb36368DFc8793 |
| create_policy_pool | 0x834d7e2697d1ae0073377b7c28af0cdc2f57d68542add8488c00875e8bb02719 |
| buy_policy | 0x6f1184e6ff295759a74b2b9e40325ee9703d67edfb5e2468225b41b967f137e4 |
| submit_claim (claim_0) | 0xe70e4f1f35d67e4c4b0c5fbd12c79ffd8d8bd4ddd25a706c1c2c3d8b4dca9fe9 |
| resolve_claim (claim_0, DENIED) | 0x620d82d4a3f12a7205ee0c9bd873ff04db0e858a671538b93085243f151d8af8 |
| submit_claim (claim_1) | 0x05f7b0815b26e3b1a0b1e3e5c887ba860c4b4cae5367edbf5f1df0a18cf249e1 |
| resolve_claim (claim_1, APPROVED) | 0xf15429fec615baa55a0869e7ea66d37eccf7f8ec71ad87806b7a880d683f7fc2 |

- claim_0: the evidence showed general flooding in Pakistan but no damage at the insured property, so validators denied it (payout 0).
- claim_1: the evidence named the insured property directly, validators approved 100% and 3 GEN was paid out. Pool balance went from 7 GEN to 4 GEN.

## Evidence note

The evidence used for claim_2 (`evidence/nowshera_flood_report.txt`) is a test fixture written for this demo, not a real news article. The claim on chain references the raw file URL in the `Naseer32/genlayer-bug-bounty` repository.

## Known limitations and next steps

This is a hackathon prototype. The deployed contract intentionally keeps the logic simple, and these are the known gaps I would close in a v2:

**Update (fixed):** payout_fraction was previously allowed to differ by up to 10 points between validators even though it set the exact escrow transfer amount. It is now constrained to one of {0, 25, 50, 75, 100} with an exact-match equivalence rule and a snap-to-nearest-tier fallback, so every validator-compatible run produces the same payout. This was flagged by a GenLayer Portal reviewer and fixed before resubmission.

1. **Repeat claims per policy.** A policyholder can file several claims under one policy, each with new evidence, until the pool is drained. The evidence-reuse guard only blocks reusing the same URL. Fix: mark the policy as claimed once a claim is approved.
2. **Claimant chooses the evidence.** Nothing stops a claimant from hosting their own "news article". Fix: per-pool `trusted_domains` allowlist, plus a prompt instruction that fetched evidence is untrusted data and must never be followed as instructions.
3. **No way for the insurer to withdraw.** There is no `close_pool` or `withdraw`, so the escrow stays locked. `POOL_CLOSED` exists but is not used yet.
4. **No waiting period or incident date.** A buyer can purchase a policy and claim immediately. Fix: add a coverage start delay and an incident date check against the evidence.

The demo evidence for claim_2 is a self-written test fixture, which is exactly the weakness described in point 2.
