#!/bin/bash

set -e

echo "=============================================="
echo "Context Foundry - Initial Setup"
echo "=============================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "✗ Docker is not running. Please start Docker first."
    exit 1
fi

echo "✓ Docker is running"
echo ""

# Start infrastructure
echo "Starting infrastructure services..."
docker-compose up -d postgres redis ollama

echo ""
echo "Waiting for databases to be healthy..."
sleep 10

# Wait for PostgreSQL
until docker-compose exec -T postgres pg_isready -U cf_user > /dev/null 2>&1; do
    echo "  Waiting for PostgreSQL..."
    sleep 2
done
echo "✓ PostgreSQL is ready"

# Load schema
echo ""
echo "Loading database schema..."
docker-compose exec -T postgres psql -U cf_user -d context_foundry < schema.sql
echo "✓ Schema loaded"

# Pull Ollama models
echo ""
echo "Pulling Ollama models (this may take a while)..."
docker-compose exec ollama ollama pull mistral:7b-instruct-q4_K_M || echo "⚠ Mistral model pull failed or timed out - will retry later"
docker-compose exec ollama ollama pull nomic-embed-text:latest || echo "⚠ Nomic embed model pull failed - will retry later"

echo ""
echo "=============================================="
echo "✓ Infrastructure setup complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "1. Build the application: docker-compose build app"
echo "2. Load walking skeleton data: docker-compose run --rm app python -m src.cli load-data"
echo "3. Promote to TRUSTED: docker-compose run --rm app python -m src.cli promote-all"
echo "4. Start the API: docker-compose up app"
echo ""
