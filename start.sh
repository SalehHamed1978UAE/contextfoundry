#!/bin/bash

echo "============================================"
echo "Context Foundry Startup Script"
echo "============================================"

CF_RUN_MODE="${CF_RUN_MODE:-serve}"
echo "[Config] CF_RUN_MODE: $CF_RUN_MODE"

export CF_TREE_BASED_RETRIEVAL=false
echo "[Config] Tree-based retrieval: $CF_TREE_BASED_RETRIEVAL (kept off 2026-05-08: chunk-grounded fallback fix unit-tested at avg sim 0.576, but full Nexus benchmark still -11 vs legacy 74; do not enable without further investigation of 14 still-failing questions)"

if [ "$CF_RUN_MODE" = "extract" ]; then
    if [ -z "$CF_EXTRACT_VAULT" ]; then
        echo "[Error] CF_EXTRACT_VAULT is required for extract mode"
        exit 1
    fi
    echo "[Extract] Running vault extraction for vault: $CF_EXTRACT_VAULT"
    python -u scripts/run_vault_extraction.py --vault-id "$CF_EXTRACT_VAULT" --use-ontology
    exit $?

elif [ "$CF_RUN_MODE" = "verify" ]; then
    if [ -z "$CF_VERIFY_TENANT" ]; then
        echo "[Error] CF_VERIFY_TENANT is required for verify mode"
        exit 1
    fi
    echo "[Verify] Running verification for tenant: $CF_VERIFY_TENANT"

    if [ "$CF_VERIFY_LOOP" = "true" ]; then
        while true; do
            python -c "
import sys, os
sys.path.insert(0, os.getcwd())
from src.context_foundry.workers.verification_worker import VerificationWorker, VerificationConfig
from src.context_foundry.agents.gardener import GardenerAgent, GardenerConfig
from src.context_foundry.models.schema import get_session
tenant_id = os.environ['CF_VERIFY_TENANT']
print('[Verify] Running VerificationWorker...')
worker = VerificationWorker(tenant_id=tenant_id, config=VerificationConfig())
stats = worker.run()
print(f'[Verify] Verification: {stats}')
print('[Verify] Running GardenerAgent.promotion_pass()...')
session = get_session()
gardener = GardenerAgent(session=session, tenant_id=tenant_id, config=GardenerConfig())
result = gardener.promotion_pass()
print(f'[Verify] Promotion: promoted={result.entities_promoted} entities, {result.relationships_promoted} relationships')
session.close()
print('[Verify] Done.')
"
            echo "[Verify] Sleeping 60s before next iteration..."
            sleep 60
        done
    else
        python -c "
import sys, os
sys.path.insert(0, os.getcwd())
from src.context_foundry.workers.verification_worker import VerificationWorker, VerificationConfig
from src.context_foundry.agents.gardener import GardenerAgent, GardenerConfig
from src.context_foundry.models.schema import get_session
tenant_id = os.environ['CF_VERIFY_TENANT']
print('[Verify] Running VerificationWorker...')
worker = VerificationWorker(tenant_id=tenant_id, config=VerificationConfig())
stats = worker.run()
print(f'[Verify] Verification: {stats}')
print('[Verify] Running GardenerAgent.promotion_pass()...')
session = get_session()
gardener = GardenerAgent(session=session, tenant_id=tenant_id, config=GardenerConfig())
result = gardener.promotion_pass()
print(f'[Verify] Promotion: promoted={result.entities_promoted} entities, {result.relationships_promoted} relationships')
session.close()
print('[Verify] Done.')
"
        exit $?
    fi

elif [ "$CF_RUN_MODE" = "serve" ]; then
    echo "[Cleanup] Killing existing service processes..."
    pkill -f "python.*brain.app" 2>/dev/null || true
    pkill -f "python.*web_app" 2>/dev/null || true
    sleep 1

    echo "[Cleanup] Killing processes on ports 3000 and 5000..."
    fuser -k 3000/tcp 2>/dev/null || true
    fuser -k 5000/tcp 2>/dev/null || true
    sleep 3

    echo "[Check] Verifying ports are available..."
    for i in 1 2 3; do
        if ! fuser 3000/tcp 2>/dev/null && ! fuser 5000/tcp 2>/dev/null; then
            echo "[Check] Ports 3000 and 5000 are available"
            break
        fi
        echo "[Check] Waiting for ports to free (attempt $i)..."
        sleep 2
    done

    echo "[Start] Starting Brain Service on port 3000..."
    cd /home/runner/workspace
    export SKIP_PORT_CHECK=1
    python brain/app.py &
    BRAIN_PID=$!
    sleep 5

    if ! kill -0 $BRAIN_PID 2>/dev/null; then
        echo "[Error] Brain Service failed to start!"
        exit 1
    fi
    echo "[Start] Brain Service started (PID: $BRAIN_PID)"

    echo "[Start] Starting Platform Service on port 5000..."
    python web_app.py &
    PLATFORM_PID=$!
    sleep 5

    if ! kill -0 $PLATFORM_PID 2>/dev/null; then
        echo "[Error] Platform Service failed to start!"
        kill $BRAIN_PID 2>/dev/null || true
        exit 1
    fi
    echo "[Start] Platform Service started (PID: $PLATFORM_PID)"

    echo "============================================"
    echo "All services started successfully!"
    echo "Brain Service: http://0.0.0.0:3000"
    echo "Platform Service: http://0.0.0.0:5000"
    echo "============================================"

    cleanup() {
        echo ""
        echo "[Shutdown] Received shutdown signal..."
        echo "[Shutdown] Stopping Brain Service (PID: $BRAIN_PID)..."
        kill $BRAIN_PID 2>/dev/null || true
        echo "[Shutdown] Stopping Platform Service (PID: $PLATFORM_PID)..."
        kill $PLATFORM_PID 2>/dev/null || true
        sleep 2
        echo "[Shutdown] All services stopped"
        exit 0
    }

    trap cleanup SIGTERM SIGINT SIGHUP

    wait $BRAIN_PID $PLATFORM_PID

else
    echo "[Error] Unknown CF_RUN_MODE: $CF_RUN_MODE (expected: serve, extract, verify)"
    exit 1
fi
