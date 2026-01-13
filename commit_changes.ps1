#!/usr/bin/env powershell
# Commit state filtering changes

$ErrorActionPreference = "Continue"

Push-Location "c:\Users\aerki\riven\trc"

try {
    Write-Host ""
    Write-Host "=====================================================================" -ForegroundColor Cyan
    Write-Host "Committing state filtering changes" -ForegroundColor Cyan
    Write-Host "=====================================================================" -ForegroundColor Cyan
    Write-Host ""
    
    # Stage all changes
    Write-Host "[1/3] Staging changes..." -ForegroundColor Yellow
    & git add -A 2>&1 | Out-Null
    Write-Host "      ✓ Staged" -ForegroundColor Green
    Write-Host ""
    
    # Create commit
    Write-Host "[2/3] Creating commit..." -ForegroundColor Yellow
    $message = @"
Enforce state filtering: only process Failed/Unknown items

- Enhanced get_problem_items() fallback to filter locally by state
- Added state re-validation in _handle_problem_item()
- Items with changed states automatically removed from tracking
- Added STATE_FILTERING.md documentation
- Created verify_states.py verification script

This ensures TRC only processes items in Failed or Unknown states from Riven,
with multiple layers of filtering and validation.
"@
    
    & git commit -m $message 2>&1 | Tee-Object -Variable commitOutput | Out-Null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "      ✓ Commit created" -ForegroundColor Green
    } else {
        Write-Host "      ✗ Commit failed" -ForegroundColor Red
        Write-Host "$commitOutput"
    }
    Write-Host ""
    
    # Show commit info
    Write-Host "[3/3] Commit details:" -ForegroundColor Yellow
    & git log --oneline -1 2>&1
    Write-Host ""
    
    Write-Host "=====================================================================" -ForegroundColor Cyan
    Write-Host "✓ COMMIT COMPLETE" -ForegroundColor Green
    Write-Host "=====================================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next: git push origin main" -ForegroundColor Gray
    
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
} finally {
    Pop-Location
}
