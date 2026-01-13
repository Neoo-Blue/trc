#!/usr/bin/env powershell
# Check what files need to be committed

$recentFiles = @(
    "src/riven_client.py",
    "src/monitor.py", 
    "STATE_FILTERING.md",
    "verify_states.py",
    "COMMIT_READY.md",
    "COMMIT_INSTRUCTIONS.md",
    "commit_changes.ps1",
    "commit.bat",
    "commit_noeditor.bat"
)

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Files to be committed:" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

$root = "c:\Users\aerki\riven\trc"
foreach ($file in $recentFiles) {
    $fullPath = Join-Path $root $file
    if (Test-Path $fullPath) {
        $lastWrite = (Get-Item $fullPath).LastWriteTime
        Write-Host "  ✓ $file" -ForegroundColor Green
        Write-Host "    Modified: $lastWrite" -ForegroundColor Gray
    } else {
        Write-Host "  ✗ $file (NOT FOUND)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "To commit all changes:" -ForegroundColor Yellow
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "cd c:\Users\aerki\riven\trc" -ForegroundColor Yellow
Write-Host "git add -A" -ForegroundColor Yellow
Write-Host "git commit -m 'Enforce state filtering: only process Failed/Unknown items...'" -ForegroundColor Yellow
Write-Host ""
