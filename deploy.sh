# deploy.sh — Deploy the full stack to Alibaba Cloud ECS
# Usage: bash deploy.sh [--build-frontend]
#
# Prerequisites:
#   1. SSH key configured for root@47.99.108.75
#   2. Docker installed on ECS
#   3. Frontend already built (`cd frontend && npm run build`) or use --build-frontend

set -e

ECS_HOST="root@47.99.108.75"
ECS_PATH="/opt/rag-deploy"

echo "=== [1/3] Building React frontend ==="
cd frontend && npm run build && cd ..

echo "=== [2/3] Uploading project to ECS ==="
ssh "$ECS_HOST" "mkdir -p $ECS_PATH"
scp -r \
    Dockerfile \
    docker-compose.yml \
    nginx.conf \
    requirements.txt \
    .env.example \
    alembic.ini \
    api.py \
    auth.py \
    celery_app.py \
    config.py \
    database.py \
    logger.py \
    metrics.py \
    middleware.py \
    models.py \
    rate_limiter.py \
    redis_client.py \
    schemas.py \
    task_queue.py \
    tasks.py \
    tracing.py \
    migrations/ \
    frontend/dist/ \
    "$ECS_HOST:$ECS_PATH"

echo "=== [3/3] Rebuilding and starting Docker services ==="
ssh "$ECS_HOST" "cd $ECS_PATH && docker compose down && docker compose up -d --build"

echo ""
echo "=== Deploy complete ==="
echo "Frontend:  http://47.99.108.75"
echo "API:       http://47.99.108.75/health"
echo "Jaeger UI: http://47.99.108.75:16686"
echo "Metrics:   http://47.99.108.75/metrics"
