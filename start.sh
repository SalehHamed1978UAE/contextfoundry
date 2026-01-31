#!/bin/bash
# Startup script with port cleanup for Context Foundry
# Prevents port conflicts by ensuring clean startup

echo "============================================"
echo "Context Foundry Startup Script"
echo "============================================"

# Kill any existing Python processes for our services
echo "[Cleanup] Killing existing service processes..."
pkill -f "python.*brain.app" 2>/dev/null || true
pkill -f "python.*web_app" 2>/dev/null || true
sleep 1

# Kill any processes on our ports
echo "[Cleanup] Killing processes on ports 3000 and 5000..."
fuser -k 3000/tcp 2>/dev/null || true
fuser -k 5000/tcp 2>/dev/null || true
sleep 3

# Verify ports are free
echo "[Check] Verifying ports are available..."
for i in 1 2 3; do
    if ! fuser 3000/tcp 2>/dev/null && ! fuser 5000/tcp 2>/dev/null; then
        echo "[Check] Ports 3000 and 5000 are available"
        break
    fi
    echo "[Check] Waiting for ports to free (attempt $i)..."
    sleep 2
done

# Start Brain Service on port 3000
echo "[Start] Starting Brain Service on port 3000..."
cd /home/runner/workspace
export SKIP_PORT_CHECK=1
python brain/app.py &
BRAIN_PID=$!
sleep 5

# Verify Brain started
if ! kill -0 $BRAIN_PID 2>/dev/null; then
    echo "[Error] Brain Service failed to start!"
    exit 1
fi
echo "[Start] Brain Service started (PID: $BRAIN_PID)"

# Start Platform Service on port 5000
echo "[Start] Starting Platform Service on port 5000..."
python web_app.py &
PLATFORM_PID=$!
sleep 5

# Verify Platform started
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

# Handle shutdown signals
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

# Wait for both processes
wait $BRAIN_PID $PLATFORM_PID
