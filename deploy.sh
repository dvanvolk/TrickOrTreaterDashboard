#!/bin/bash
set -e

# --- Configuration ---
PROJECT_DIR="/home/dan/trickortreat-dashboard/TrickOrTreaterDashboard"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"

echo "🔄 Starting deployment of Trick or Treat Dashboard..."

# Step 1: Navigate to project directory
cd "$PROJECT_DIR"

# Step 2: Pull latest changes from Git
echo "📦 Pulling latest code from Git..."
git fetch origin
git reset --hard origin/main

# Step 3: Stop existing containers
echo "🧱 Stopping existing containers..."
docker compose -f "$COMPOSE_FILE" down

# Step 4: Remove old dangling images (optional cleanup)
echo "🧹 Cleaning up old Docker images..."
docker image prune -f

# Step 5: Rebuild and start containers
echo "🚀 Rebuilding and starting Docker containers..."
docker compose -f "$COMPOSE_FILE" up -d --build

# Step 6: Verify status
echo "🩺 Checking container health..."
docker compose -f "$COMPOSE_FILE" ps

echo "✅ Deployment completed successfully!"
