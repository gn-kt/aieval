# deploy_to_ecs.ps1 — 一键部署 backend-stage3-alembic 到阿里云 ECS
# 用法：在 PowerShell 中执行 .\deploy_to_ecs.ps1

$ErrorActionPreference = "Stop"
$ECS_HOST = "root@47.99.108.75"
$ECS_PATH = "/opt/rag-deploy"
$LOCAL_PATH = "D:\codebase\AI_project\backend-stage3-alembic"
$SSH_OPTS = "-o ServerAliveInterval=30 -o ServerAliveCountMax=3"

# ============================================================
# [1/5] Build React frontend
# ============================================================
Write-Host "`n=== [1/5] Building React frontend ===" -ForegroundColor Cyan
Set-Location "$LOCAL_PATH\frontend"
npm run build
Set-Location $LOCAL_PATH

# ============================================================
# [2/5] Upload source code to ECS
# ============================================================
Write-Host "`n=== [2/5] Uploading project files ===" -ForegroundColor Cyan
ssh $SSH_OPTS $ECS_HOST "mkdir -p $ECS_PATH/frontend $ECS_PATH/rag $ECS_PATH/notes $ECS_PATH/migrations/versions"

# frontend dist (tar to avoid path issues)
Write-Host "  Packing frontend dist..."
Set-Location "$LOCAL_PATH\frontend"
tar -czf dist.tar.gz dist
scp dist.tar.gz "${ECS_HOST}:${ECS_PATH}/frontend/"
Remove-Item dist.tar.gz
Set-Location $LOCAL_PATH

# Python source files
scp -r `
    "$LOCAL_PATH\Dockerfile" `
    "$LOCAL_PATH\docker-compose.yml" `
    "$LOCAL_PATH\nginx.conf" `
    "$LOCAL_PATH\requirements.txt" `
    "$LOCAL_PATH\alembic.ini" `
    "$LOCAL_PATH\api.py" `
    "$LOCAL_PATH\auth.py" `
    "$LOCAL_PATH\celery_app.py" `
    "$LOCAL_PATH\config.py" `
    "$LOCAL_PATH\database.py" `
    "$LOCAL_PATH\logger.py" `
    "$LOCAL_PATH\metrics.py" `
    "$LOCAL_PATH\middleware.py" `
    "$LOCAL_PATH\models.py" `
    "$LOCAL_PATH\rate_limiter.py" `
    "$LOCAL_PATH\redis_client.py" `
    "$LOCAL_PATH\schemas.py" `
    "$LOCAL_PATH\session_manager.py" `
    "$LOCAL_PATH\task_queue.py" `
    "$LOCAL_PATH\tasks.py" `
    "$LOCAL_PATH\tracing.py" `
    "$LOCAL_PATH\migrations\" `
    "$LOCAL_PATH\rag\" `
    "${ECS_HOST}:${ECS_PATH}/"

# Knowledge base notes (Obsidian AI Agent notes)
Write-Host "  Uploading knowledge base notes..."
scp -r "$LOCAL_PATH\notes\*.md" "${ECS_HOST}:${ECS_PATH}/notes/"

# ============================================================
# [3/5] Upload .env (must exist locally)
# ============================================================
Write-Host "`n=== [3/5] Uploading .env ===" -ForegroundColor Cyan
if (-not (Test-Path "$LOCAL_PATH\.env")) {
    Write-Host "  ERROR: .env not found. Create it from .env.example first." -ForegroundColor Red
    Write-Host "  Required: DEEPSEEK_API_KEY, ALIYUN_API_KEY" -ForegroundColor Yellow
    exit 1
}
scp "$LOCAL_PATH\.env" "${ECS_HOST}:${ECS_PATH}/"

# ============================================================
# [4/5] Docker rebuild + start
# ============================================================
Write-Host "`n=== [4/5] Rebuilding Docker services ===" -ForegroundColor Cyan
ssh $SSH_OPTS $ECS_HOST @"
cd $ECS_PATH/frontend
echo "--- Extracting frontend dist ---"
rm -rf dist
tar -xzf dist.tar.gz
rm dist.tar.gz

cd $ECS_PATH
echo "--- Stopping old containers ---"
docker compose down 2>/dev/null
echo "--- Cleaning build cache ---"
docker builder prune -f 2>/dev/null
echo "--- Building and starting all services ---"
docker compose up -d --build
echo ""
echo "--- Container status ---"
docker ps --format "table {{.Names}}\t{{.Status}}"
"@

# ============================================================
# [5/5] Post-deploy: wait, then run migrations + ingest
# ============================================================
Write-Host "`n=== [5/5] Post-deploy initialization ===" -ForegroundColor Cyan
ssh $SSH_OPTS $ECS_HOST @"
echo "--- Waiting for API to be ready ---"
for i in \$(seq 1 30); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "API ready after \${i}s"
        break
    fi
    sleep 2
done

echo "--- Running Alembic migrations ---"
docker exec rag-api alembic upgrade head 2>/dev/null || echo "Migration skipped (db already up to date)"

echo "--- Ingesting knowledge base into ChromaDB ---"
docker exec rag-api python -m rag.ingest

echo ""
echo "--- API health check ---"
curl -s http://localhost:8000/health
"@

Write-Host "`n=== Deploy complete ===" -ForegroundColor Green
Write-Host "Frontend:  http://47.99.108.75"
Write-Host "Jaeger UI: http://47.99.108.75:16686"
Write-Host "API:       http://47.99.108.75/health"
Write-Host ""
Write-Host "First-time setup on ECS: ssh root@47.99.108.75"
Write-Host "  - View logs:  docker logs rag-api --tail 50"
Write-Host "  - Restart:    docker compose restart api"
Write-Host "  - Re-ingest:  docker exec rag-api python -m rag.ingest"
