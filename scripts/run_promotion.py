"""
One-shot Gardener promotion pass for a vault.

Uses RLS-scoped session (admin role bypasses RLS but we filter by tenant
explicitly via direct SQL count first). Calls GardenerAgent.promotion_pass
inside a tenant_session so the agent's tenantless queries are scoped via RLS.
"""
import argparse
import json

from src.context_foundry.models.schema import tenant_session
from src.context_foundry.agents.gardener import GardenerAgent, GardenerConfig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant-id", required=True)
    args = ap.parse_args()

    cfg = GardenerConfig()
    with tenant_session(args.tenant_id, role='user') as ts:
        agent = GardenerAgent(session=ts._session, config=cfg)
        result = agent.promotion_pass(cycle_id=f"manual-{args.tenant_id[:8]}")
        ts._session.commit()
    print(json.dumps(result.to_dict(), indent=2, default=str))


if __name__ == "__main__":
    main()
