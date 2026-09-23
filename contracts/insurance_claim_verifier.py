# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import re
import json
import hashlib

POOL_OPEN = "open"
POOL_CLOSED = "closed"

CLAIM_PENDING = "pending"
CLAIM_APPROVED = "approved"
CLAIM_DENIED = "denied"
CLAIM_APPROVED_NO_FUNDS = "approved_no_funds"

URL_RE = re.compile(r"^https://[^\s|]+$")


class InsuranceClaimVerifier(gl.Contract):
    pool_count: u256
    claim_count: u256
    pools: str              # JSON: {pool_id: {...}}
    claims: str             # JSON: {claim_id: {...}}
    policyholders: str      # JSON: {"pool_id:0xaddr": "1"}
    evidence_registry: str  # JSON: {sha256(url): claim_id}   (fraud guard)

    def __init__(self):
        self.pool_count = u256(0)
        self.claim_count = u256(0)
        self.pools = "{}"
        self.claims = "{}"
        self.policyholders = "{}"
        self.evidence_registry = "{}"

    # ---------- Insurer: create a pool ----------
    @gl.public.write.payable
    def create_policy_pool(
        self,
        name: str,
        terms_text: str,
        premium_wei: str,
        max_payout_wei: str,
    ) -> str:
        amount = gl.message.value
        if amount == u256(0):
            raise Exception("Pool must be funded with an initial GEN escrow")
        if int(premium_wei) <= 0 or int(max_payout_wei) <= 0:
            raise Exception("premium_wei and max_payout_wei must be > 0")

        pools = json.loads(self.pools)

        pool_id = f"pool_{int(self.pool_count)}"
        self.pool_count = u256(int(self.pool_count) + 1)

        pools[pool_id] = {
            "insurer": gl.message.sender_address.as_hex,
            "name": name,
            "terms_text": terms_text,
            "premium_wei": premium_wei,
            "max_payout_wei": max_payout_wei,
            "balance_wei": str(int(amount)),
            "status": POOL_OPEN,
        }
        self.pools = json.dumps(pools, sort_keys=True)
        return pool_id

    # ---------- Buyer: purchase coverage ----------
    @gl.public.write.payable
    def buy_policy(self, pool_id: str) -> None:
        pools = json.loads(self.pools)
        pool = pools.get(pool_id)
        if pool is None:
            raise Exception("Pool does not exist")
        if pool["status"] != POOL_OPEN:
            raise Exception("Pool is closed")

        buyer = gl.message.sender_address.as_hex
        key = f"{pool_id}:{buyer}"

        policyholders = json.loads(self.policyholders)
        if policyholders.get(key) is not None:
            raise Exception("Already insured under this pool")

        amount = gl.message.value
        if int(amount) != int(pool["premium_wei"]):
            raise Exception("Sent value must exactly match premium_wei")

        pool["balance_wei"] = str(int(pool["balance_wei"]) + int(amount))
        pools[pool_id] = pool
        self.pools = json.dumps(pools, sort_keys=True)

        policyholders[key] = "1"
        self.policyholders = json.dumps(policyholders, sort_keys=True)

    # ---------- Policyholder: file a claim ----------
    @gl.public.write
    def submit_claim(self, pool_id: str, description: str, evidence_urls: str) -> str:
        pools = json.loads(self.pools)
        if pools.get(pool_id) is None:
            raise Exception("Pool does not exist")

        claimant = gl.message.sender_address.as_hex
        key = f"{pool_id}:{claimant}"

        policyholders = json.loads(self.policyholders)
        if policyholders.get(key) is None:
            raise Exception("Caller is not insured under this pool")

        urls = [u.strip() for u in evidence_urls.split("|") if u.strip()]
        if len(urls) == 0:
            raise Exception("At least one evidence URL is required")
        for u in urls:
            if not URL_RE.match(u):
                raise Exception(f"Invalid evidence URL: {u}")

        claims = json.loads(self.claims)

        claim_id = f"claim_{int(self.claim_count)}"
        self.claim_count = u256(int(self.claim_count) + 1)

        claims[claim_id] = {
            "pool_id": pool_id,
            "claimant": claimant,
            "description": description,
            "evidence_urls": urls,
            "status": CLAIM_PENDING,
            "reason": "",
            "payout_wei": "0",
        }
        self.claims = json.dumps(claims, sort_keys=True)
        return claim_id

    # ---------- Anyone: trigger adjudication (permissionless, AI decides) ----------
    @gl.public.write
    def resolve_claim(self, claim_id: str) -> None:
        claims = json.loads(self.claims)
        claim = claims.get(claim_id)
        if claim is None:
            raise Exception("Claim does not exist")
        if claim["status"] != CLAIM_PENDING:
            raise Exception("Claim already resolved")

        pools = json.loads(self.pools)
        pool = pools.get(claim["pool_id"])
        if pool is None:
            raise Exception("Pool does not exist")

        # --- Deterministic fraud guard: evidence reuse across claims ---
        evidence_registry = json.loads(self.evidence_registry)
        for url in claim["evidence_urls"]:
            h = hashlib.sha256(url.encode()).hexdigest()
            prior = evidence_registry.get(h)
            if prior is not None and prior != claim_id:
                claim["status"] = CLAIM_DENIED
                claim["reason"] = f"Evidence URL already used in {prior} (reuse suspected)"
                claims[claim_id] = claim
                self.claims = json.dumps(claims, sort_keys=True)
                return

        for url in claim["evidence_urls"]:
            h = hashlib.sha256(url.encode()).hexdigest()
            evidence_registry[h] = claim_id
        self.evidence_registry = json.dumps(evidence_registry, sort_keys=True)

        # --- Capture into locals before the nondet block (storage reads inside it are unsafe) ---
        terms_text = pool["terms_text"]
        description = claim["description"]
        evidence_urls = list(claim["evidence_urls"])

        def get_decision() -> str:
            evidence_text = ""
            for u in evidence_urls:
                try:
                    page = gl.nondet.web.render(u, mode="text")
                except Exception:
                    page = "[FETCH_FAILED]"
                evidence_text += f"\n--- Evidence from {u} ---\n{page[:4000]}\n"

            prompt = (
                "You are adjudicating an insurance claim. Judge strictly against the "
                "policy terms below. Only approve if the evidence clearly satisfies "
                "every requirement stated in the terms.\n\n"
                f"POLICY TERMS:\n{terms_text}\n\n"
                f"CLAIM DESCRIPTION:\n{description}\n\n"
                f"EVIDENCE:\n{evidence_text}\n\n"
                "Respond with ONLY raw JSON, no markdown, no code fences, in exactly "
                "this shape: "
                '{"decision": "approved" or "denied", "payout_fraction": integer 0-100, '
                '"reason": "one or two sentences"}'
            )
            raw = str(gl.nondet.exec_prompt(prompt))
            return raw.replace("```json", "").replace("```", "").strip()

        result_str = gl.eq_principle.prompt_comparative(
            get_decision,
            "The decision (approved/denied) must match exactly, and payout_fraction "
            "must be within 10 of each other.",
        )

        try:
            parsed = json.loads(result_str)
            decision = str(parsed.get("decision", "denied")).lower()
            fraction = int(parsed.get("payout_fraction", 0))
            reason = str(parsed.get("reason", ""))
        except Exception:
            decision = "denied"
            fraction = 0
            reason = "Could not parse validator decision"

        fraction = max(0, min(100, fraction))

        if decision != "approved" or fraction == 0:
            claim["status"] = CLAIM_DENIED
            claim["reason"] = reason or "Claim denied by AI adjudication"
            claims[claim_id] = claim
            self.claims = json.dumps(claims, sort_keys=True)
            return

        payout_wei = (int(pool["max_payout_wei"]) * fraction) // 100

        if payout_wei > int(pool["balance_wei"]):
            claim["status"] = CLAIM_APPROVED_NO_FUNDS
            claim["reason"] = f"Approved ({fraction}%) but pool has insufficient balance"
            claims[claim_id] = claim
            self.claims = json.dumps(claims, sort_keys=True)
            return

        pool["balance_wei"] = str(int(pool["balance_wei"]) - payout_wei)
        pools[claim["pool_id"]] = pool
        self.pools = json.dumps(pools, sort_keys=True)

        claim["status"] = CLAIM_APPROVED
        claim["reason"] = reason
        claim["payout_wei"] = str(payout_wei)
        claims[claim_id] = claim
        self.claims = json.dumps(claims, sort_keys=True)

        recipient = gl.get_contract_at(Address(claim["claimant"]))
        recipient.emit_transfer(value=u256(payout_wei))

    # ---------- Views ----------
    @gl.public.view
    def get_pools(self) -> str:
        return self.pools

    @gl.public.view
    def get_claims(self) -> str:
        return self.claims

    @gl.public.view
    def get_pool(self, pool_id: str) -> str:
        pools = json.loads(self.pools)
        pool = pools.get(pool_id)
        if pool is None:
            raise Exception("Pool does not exist")
        return json.dumps(pool)

    @gl.public.view
    def get_claim(self, claim_id: str) -> str:
        claims = json.loads(self.claims)
        claim = claims.get(claim_id)
        if claim is None:
            raise Exception("Claim does not exist")
        return json.dumps(claim)
