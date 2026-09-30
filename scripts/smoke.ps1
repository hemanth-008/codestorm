<#
.SYNOPSIS
  FleetTwin end-to-end smoke test (A6 hardening).

.DESCRIPTION
  Checks: /health, /api/stream (ingest), /api/fleet (twin sync),
  inject noise + verify event, inject dropout + recovery, /api/missions/simulate,
  /api/eval/run, /metrics.  Returns exit code 0 on success, 1 on any failure.

  The backend must already be running on http://127.0.0.1:8000.
#>
$ErrorActionPreference = 'Stop'
$base = 'http://127.0.0.1:8000'
$fail = 0

function Assert-True($condition, $msg) {
    if (-not $condition) {
        Write-Host "FAIL: $msg" -ForegroundColor Red
        $script:fail++
    } else {
        Write-Host "PASS: $msg" -ForegroundColor Green
    }
}

# ---- 1. Health endpoint ----
Write-Host "`n=== 1. /health ===" -ForegroundColor Cyan
try {
    $h = Invoke-RestMethod -Uri "$base/health"
    Assert-True ($h.status -eq 'ok') '/health returns status=ok'
} catch {
    Assert-True $false "/health reachable: $_"
}

# ---- 2. Ingest (SSE stream delivers at least one frame within 5s) ----
Write-Host "`n=== 2. SSE /api/stream ===" -ForegroundColor Cyan
try {
    $job = Start-Job -ScriptBlock {
        param($url)
        $req = [System.Net.HttpWebRequest]::Create($url)
        $req.Timeout = 5000
        $resp = $req.GetResponse()
        $reader = New-Object System.IO.StreamReader($resp.GetResponseStream())
        $line = $reader.ReadLine()
        $reader.Close(); $resp.Close()
        return $line
    } -ArgumentList "$base/api/stream"
    $result = $job | Wait-Job -Timeout 8 | Receive-Job
    Assert-True ($result -match '"robots"') 'SSE stream emits a frame with robots'
} catch {
    Assert-True $false "SSE stream: $_"
}

# ---- 3. Fleet twin sync ----
Write-Host "`n=== 3. /api/fleet twin sync ===" -ForegroundColor Cyan
try {
    $fleet = Invoke-RestMethod -Uri "$base/api/fleet"
    $synced = @($fleet | Where-Object { $_.twin.sync_score -gt 50 })
    Assert-True ($synced.Count -ge 1) "At least 1 robot with sync > 50 (got $($synced.Count))"
} catch {
    Assert-True $false "/api/fleet: $_"
}

# ---- 4. Inject noise and check for event ----
Write-Host "`n=== 4. Inject noise ===" -ForegroundColor Cyan
try {
    $body = @{ robot_id='R1'; kind='noise'; magnitude=5.0; duration_s=3.0 } | ConvertTo-Json
    Invoke-RestMethod -Uri "$base/api/attacks/inject" -Method Post -Body $body -ContentType 'application/json' | Out-Null
    Start-Sleep -Seconds 4
    $events = Invoke-RestMethod -Uri "$base/api/events?limit=50"
    $noiseEvt = @($events | Where-Object { $_.kind -eq 'noise_high' -and $_.robot_id -eq 'R1' })
    Assert-True ($noiseEvt.Count -ge 1) 'noise injection produces noise_high event'
    Invoke-RestMethod -Uri "$base/api/attacks/clear" -Method Post -Body '{}' -ContentType 'application/json' | Out-Null
} catch {
    Assert-True $false "noise injection: $_"
}

# ---- 5. Inject dropout and check recovery ----
Write-Host "`n=== 5. Inject dropout ===" -ForegroundColor Cyan
try {
    $body = @{ robot_id='D1'; kind='dropout'; magnitude=1.0; duration_s=3.0 } | ConvertTo-Json
    Invoke-RestMethod -Uri "$base/api/attacks/inject" -Method Post -Body $body -ContentType 'application/json' | Out-Null
    Start-Sleep -Seconds 5
    $events = Invoke-RestMethod -Uri "$base/api/events?limit=100"
    $dropEvt = @($events | Where-Object { $_.kind -eq 'dropout' -and $_.robot_id -eq 'D1' })
    $recEvt  = @($events | Where-Object { $_.kind -eq 'link_recovered' -and $_.robot_id -eq 'D1' })
    Assert-True ($dropEvt.Count -ge 1) 'dropout injection produces dropout event'
    Assert-True ($recEvt.Count -ge 1)  'link_recovered event fires after dropout ends'
    Invoke-RestMethod -Uri "$base/api/attacks/clear" -Method Post -Body '{}' -ContentType 'application/json' | Out-Null
} catch {
    Assert-True $false "dropout injection: $_"
}

# ---- 6. Mission simulate ----
Write-Host "`n=== 6. /api/missions/simulate ===" -ForegroundColor Cyan
try {
    $mission = @{
        mission_id = 'smoke-test'
        robot_id   = 'G1'
        waypoints  = @(
            @{ x=50; y=50; z=0 },
            @{ x=150; y=50; z=0 },
            @{ x=150; y=150; z=0 }
        )
        cruise_speed = 2.0
        loop = $false
    } | ConvertTo-Json -Depth 3
    $sim = Invoke-RestMethod -Uri "$base/api/missions/simulate" -Method Post -Body $mission -ContentType 'application/json'
    Assert-True ($sim.eta_s -gt 0)    "SimResult eta_s > 0 (got $($sim.eta_s))"
    Assert-True ($null -ne $sim.path) 'SimResult has a path'
} catch {
    Assert-True $false "mission simulate: $_"
}

# ---- 7. Eval suite ----
Write-Host "`n=== 7. /api/eval/run ===" -ForegroundColor Cyan
try {
    $eval = Invoke-RestMethod -Uri "$base/api/eval/run?seed=42" -Method Post
    Assert-True ($eval.rows.Count -ge 5) "eval rows >= 5 (got $($eval.rows.Count))"
    Assert-True ($eval.summary.detection_rate -ge 0.5) "detection_rate >= 50% (got $($eval.summary.detection_rate))"
} catch {
    Assert-True $false "eval suite: $_"
}

# ---- 8. Metrics ----
Write-Host "`n=== 8. /metrics ===" -ForegroundColor Cyan
try {
    $m = (Invoke-WebRequest -Uri "$base/metrics" -UseBasicParsing).Content
    Assert-True ($m -match 'fleettwin_requests_total') '/metrics contains Prometheus counters'
} catch {
    Assert-True $false "/metrics: $_"
}

# ---- Summary ----
Write-Host "`n=============================="
if ($fail -eq 0) {
    Write-Host "ALL CHECKS PASSED" -ForegroundColor Green
    exit 0
} else {
    Write-Host "$fail CHECK(S) FAILED" -ForegroundColor Red
    exit 1
}
