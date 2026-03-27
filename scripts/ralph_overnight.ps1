# Ralph Overnight TTS Quality Loop
# Runs ralph_tts_loop.py --rounds 1 continuously until stop time
# Auto-commits and pushes every 5 rounds
# Auto-restarts server between rounds

$ErrorActionPreference = "Continue"
$python = "C:\.pyenv\pyenv-win\versions\3.11.9\python.exe"
$dir = "C:\Users\Vketh\Desktop\Mario_AI"
$logFile = "$dir\ralph_overnight_log.txt"
$stopTime = [DateTime]::Parse("2026-03-12 07:00:00")  # 7 AM EST

Set-Location $dir

function Log($msg) {
    $ts = Get-Date -Format "HH:mm:ss"
    $line = "[$ts] $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line
}

function Ensure-Server {
    # Check if server is up
    try {
        Invoke-RestMethod http://localhost:8765/health -TimeoutSec 5 | Out-Null
        Invoke-RestMethod "http://localhost:8765/pause_idle?pause=true" -TimeoutSec 3 | Out-Null
        return $true
    } catch {}

    # Server is down — start it
    Log "Server DOWN, starting fresh..."
    Get-Process python -EA SilentlyContinue | ForEach {
        try { Stop-Process -Id $_.Id -Force -EA SilentlyContinue } catch {}
    }
    Start-Sleep 3

    Start-Process cmd -ArgumentList "/c","cd /d $dir && $python server/main.py > server_startup.log 2>&1" -WindowStyle Minimized

    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep 3
        try {
            Invoke-RestMethod http://localhost:8765/health -TimeoutSec 5 | Out-Null
            Invoke-RestMethod "http://localhost:8765/pause_idle?pause=true" -TimeoutSec 3 | Out-Null
            Log "Server UP after $($i*3)s"
            return $true
        } catch {}
    }
    Log "FATAL: Server failed to start after 3 minutes"
    return $false
}

function Git-Commit-Push($roundNum, $score) {
    Set-Location $dir
    & git add ralph_tts_results.json 2>&1 | Out-Null
    $msg = "R${roundNum}: ${score}% (overnight loop)`n`nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
    & git commit -m $msg 2>&1 | Out-Null
    # Try to push (may fail if no remote configured, that's OK)
    & git push 2>&1 | Out-Null
    Log "Committed R$roundNum ($score%)"
}

# --- Main Loop ---
Log "=== RALPH OVERNIGHT LOOP STARTED ==="
Log "Stop time: $($stopTime.ToString('yyyy-MM-dd HH:mm:ss'))"
Log "Current time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

$roundsSinceCommit = 0
$totalRounds = 0
$bestScore = 0

while ((Get-Date) -lt $stopTime) {
    $remaining = $stopTime - (Get-Date)
    Log "--- Time remaining: $([math]::Round($remaining.TotalHours,1))h ---"

    # Ensure server is running
    if (-not (Ensure-Server)) {
        Log "Server start failed, waiting 30s and retrying..."
        Start-Sleep 30
        continue
    }

    # Run one full-test round
    $totalRounds++
    Log "Starting round (total #$totalRounds)..."

    $outFile = "$dir\ralph_overnight_r_out.txt"

    # Run ralph directly (no Tee-Object — it causes crashes!)
    & $python -u ralph_tts_loop.py --rounds 1 > $outFile 2>&1

    # Parse score from output file
    $score = "?"
    $roundNum = "?"
    if (Test-Path $outFile) {
        $lines = Get-Content $outFile
        $scoreLine = $lines | Select-String "Quality:" | Select -Last 1
        $roundLine = $lines | Select-String "Rounds completed:" | Select -Last 1
        if ($scoreLine -and $scoreLine.Line -match '(\d+\.?\d*)%') {
            $score = $Matches[1]
        }
        if ($roundLine -and $roundLine.Line -match '(\d+)') {
            $roundNum = $Matches[1]
        }
    }

    Log "Round R$roundNum complete: $score%"

    if ($score -ne "?" -and [double]$score -gt $bestScore) {
        $bestScore = [double]$score
        Log "*** NEW BEST: $score% ***"
    }

    $roundsSinceCommit++

    # Commit every 5 rounds
    if ($roundsSinceCommit -ge 5) {
        Git-Commit-Push $roundNum $score
        $roundsSinceCommit = 0
    }

    # Brief pause between rounds
    Start-Sleep 5
}

# Final commit
if ($roundsSinceCommit -gt 0) {
    $lastRound = & python -c "import json; d=json.load(open('ralph_tts_results.json')); print(len(d['rounds']))"
    Git-Commit-Push $lastRound "final"
}

Log "=== RALPH OVERNIGHT LOOP FINISHED ==="
Log "Total rounds run: $totalRounds"
Log "Best score seen: $bestScore%"
Log "Stop time reached: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
