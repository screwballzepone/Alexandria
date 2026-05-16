# overnight.ps1 — JANUS Autonomous Overnight Queue Runner
# Invoked by Windows Task Scheduler nightly
# Logs to MagnumOpus/logs/overnight-<date>.log

param(
    [string]$Repo = "screwballzepone/Alexandria",
    [switch]$DryRun
)

$date = Get-Date -Format "yyyy-MM-dd"
$logDir = Join-Path -Path $PSScriptRoot -ChildPath "..\logs"
$logFile = Join-Path -Path $logDir -ChildPath "overnight-$date.log"

# Ensure log directory exists
if (-not (Test-Path -LiteralPath $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp $Message" | Out-File -FilePath $logFile -Encoding utf8 -Append
    Write-Output "$timestamp $Message"
}

function Notify-Desktop {
    param([string]$Message)
    # Try modern toast notification; fall back to msg.exe
    try {
        Add-Type -AssemblyName System.Windows.Forms
        $notify = New-Object System.Windows.Forms.NotifyIcon
        $notify.Icon = [System.Drawing.SystemIcons]::Information
        $notify.BalloonTipTitle = "JANUS Overnight Queue"
        $notify.BalloonTipText = $Message
        $notify.Visible = $true
        $notify.ShowBalloonTip(5000)
        Start-Sleep -Seconds 1
        $notify.Dispose()
    }
    catch {
        msg * "JANUS Overnight Queue: $Message" 2>&1 | Out-Null
    }
}

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
Write-Log "=== JANUS Overnight Queue Run: $date ==="

# Ensure gh CLI is available
$ghAvailable = Get-Command gh -ErrorAction SilentlyContinue
if (-not $ghAvailable) {
    Write-Log "FATAL: gh CLI not found in PATH"
    Notify-Desktop "FATAL: gh CLI not found"
    exit 1
}

# Ensure opencode.cmd is available
$opencodeAvailable = Get-Command opencode.cmd -ErrorAction SilentlyContinue
if (-not $opencodeAvailable) {
    Write-Log "FATAL: opencode.cmd not found in PATH"
    Notify-Desktop "FATAL: opencode.cmd not found"
    exit 1
}

if ($DryRun) {
    Write-Log "DRY RUN — skipping execution"
    Notify-Desktop "Dry run completed. See log for details."
    exit 0
}

# ---------------------------------------------------------------------------
# Step 1: Start opencode serve
# ---------------------------------------------------------------------------
Write-Log "Starting opencode serve..."
$serve = Start-Process opencode.cmd -ArgumentList "serve" -NoNewWindow -PassThru
Start-Sleep -Seconds 5

if ($serve.HasExited) {
    Write-Log "FATAL: opencode serve failed to start"
    Notify-Desktop "FATAL: opencode serve failed to start"
    exit 1
}
Write-Log "opencode serve started (PID: $($serve.Id))"

# ---------------------------------------------------------------------------
# Step 2: Pre-flight — clean working tree
# ---------------------------------------------------------------------------
Write-Log "Stashing any working tree changes..."
git stash 2>&1 | Out-File -FilePath $logFile -Encoding utf8 -Append

# ---------------------------------------------------------------------------
# Step 3: Scan issues
# ---------------------------------------------------------------------------
Write-Log "Running /issue-scan..."
opencode.cmd run "/issue-scan" --format json 2>&1 | Out-File -FilePath $logFile -Encoding utf8 -Append
$scanExit = $LASTEXITCODE
if ($scanExit -ne 0) {
    Write-Log "WARNING: /issue-scan exited with code $scanExit — continuing anyway"
}

# ---------------------------------------------------------------------------
# Step 4: Run queue
# ---------------------------------------------------------------------------
Write-Log "Running /issue-run..."
opencode.cmd run "/issue-run" --format json 2>&1 | Out-File -FilePath $logFile -Encoding utf8 -Append
$runExit = $LASTEXITCODE
Write-Log "/issue-run completed with exit code $runExit"

# ---------------------------------------------------------------------------
# Step 5: Restore stash
# ---------------------------------------------------------------------------
Write-Log "Restoring working tree from stash..."
git stash pop 2>&1 | Out-File -FilePath $logFile -Encoding utf8 -Append

# ---------------------------------------------------------------------------
# Step 6: Stop opencode serve
# ---------------------------------------------------------------------------
Write-Log "Stopping opencode serve..."
Get-Process opencode -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Log "opencode serve stopped."

# ---------------------------------------------------------------------------
# Notify and exit
# ---------------------------------------------------------------------------
$exitCode = if ($runExit -eq 0) { 0 } else { 1 }
if ($exitCode -eq 0) {
    Notify-Desktop "Overnight run completed successfully. See morning report for $date."
}
else {
    Notify-Desktop "Overnight run completed with errors (exit code $runExit). Check logs."
}

Write-Log "=== JANUS Overnight Queue Run Complete (exit $exitCode) ==="
exit $exitCode
