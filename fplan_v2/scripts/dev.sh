#!/bin/bash
set -e

echo "Starting FPlan v2 development environment..."

# Navigate to project root
cd "$(dirname "$0")/../.."

# Check for .env file
if [ ! -f fplan_v2/.env ]; then
    echo "Warning: fplan_v2/.env not found. Copy from fplan_v2/.env.example"
fi

# Start backend
echo "Starting FastAPI backend on :8000..."
python -m fplan_v2.api.main &
BACKEND_PID=$!

# Wait for backend to be ready
echo "Waiting for backend..."
for i in {1..10}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "Backend ready!"
        break
    fi
    sleep 1
done

# Start frontend
echo "Starting React frontend..."
cd fplan_v2/frontend
npm run dev &
FRONTEND_PID=$!

# Cleanup on exit
trap "echo 'Shutting down...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM EXIT

echo ""
echo "FPlan v2 running:"
echo "  Frontend: http://localhost:3000"
echo "  Backend:  http://localhost:8000"
echo "  API Docs: http://localhost:8000/api/docs"
echo ""
echo "Press Ctrl+C to stop."

wait
