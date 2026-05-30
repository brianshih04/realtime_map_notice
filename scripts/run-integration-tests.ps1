# run-integration-tests.ps1
# Cross-service integration tests — requires docker compose up first.

Write-Host "=== Starting integration test environment ==="
docker compose up -d --build

Write-Host "=== Waiting for services to be healthy ==="
do {
    $r1 = try { (Invoke-WebRequest -Uri http://localhost:8001/healthz -TimeoutSec 2).StatusCode } catch { 0 }
    $r2 = try { (Invoke-WebRequest -Uri http://localhost:8002/healthz -TimeoutSec 2).StatusCode } catch { 0 }
    $r3 = try { (Invoke-WebRequest -Uri http://localhost:8003/healthz -TimeoutSec 2).StatusCode } catch { 0 }
    Write-Host "  location: $r1  event: $r2  notification: $r3"
    if ($r1 -ne 200 -or $r2 -ne 200 -or $r3 -ne 200) {
        Start-Sleep -Seconds 2
    }
} while ($r1 -ne 200 -or $r2 -ne 200 -or $r3 -ne 200)

Write-Host "=== All services ready. Running cross-service integration tests ==="
pytest tests/integration/cross_service/ -v --timeout=30
$exitCode = $LASTEXITCODE

Write-Host "=== Cleaning up ==="
docker compose down

exit $exitCode
