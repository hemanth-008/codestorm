# smoke.ps1
$ErrorActionPreference = "Stop"

Write-Host "Starting backend server..."
$serverJob = Start-Job -ScriptBlock {
    Set-Location "C:\dev\ft-core\backend"
    & C:\dev\codestorm\backend\venv\Scripts\python.exe -m uvicorn main:app --port 8000
}

# Wait for server to start
Start-Sleep -Seconds 3

try {
    Write-Host "Checking /api/fleet..."
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/fleet"
    if ($response.Count -eq 0) {
        throw "Expected some robots in fleet!"
    }
    Write-Host "Fleet OK. Found $($response.Count) robots."

    Write-Host "Checking /api/robots/R1..."
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/robots/R1"
    if (-not $response.frame) {
        throw "Expected frame for R1!"
    }
    Write-Host "Robot R1 OK."

    Write-Host "Injecting fault (dropout)..."
    $body = @{
        robot_id = "R1"
        kind = "dropout"
        magnitude = 1.0
        duration_s = 2.0
    } | ConvertTo-Json
    Invoke-RestMethod -Uri "http://localhost:8000/api/attacks/inject" -Method Post -Body $body -ContentType "application/json"
    Write-Host "Fault injected."
    
    # Wait for dropout to trigger dead_reckoning event
    Start-Sleep -Seconds 3

    Write-Host "Checking /api/events..."
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/events"
    Write-Host "Found $($response.Count) events."

    Write-Host "Smoke test PASSED!"
} finally {
    Write-Host "Stopping server..."
    Stop-Job $serverJob
    Remove-Job $serverJob
}
