#!/usr/bin/env powershell
# Git operations script with proper environment handling

$env:GIT_EDITOR = "true"
$env:GIT_PAGER = "cat"

Push-Location "c:\Users\aerki\riven\trc"

try {
    Write-Host "=" * 60
    Write-Host "Synchronizing with remote repository..."
    Write-Host "=" * 60
    Write-Host ""
    
    # Fetch without pager
    Write-Host "[1/3] Fetching from remote..."
    & git fetch origin main --quiet
    Write-Host "      ✓ Fetch complete"
    Write-Host ""
    
    # Rebase to avoid merge conflicts
    Write-Host "[2/3] Rebasing local commits..."
    $result = & git rebase origin/main 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "      ✓ Rebase complete"
    } else {
        Write-Host "      ⚠ Rebase status: $result"
    }
    Write-Host ""
    
    # Push to remote
    Write-Host "[3/3] Pushing to remote..."
    & git push origin main --quiet
    Write-Host "      ✓ Push complete"
    Write-Host ""
    
    Write-Host "=" * 60
    Write-Host "✓ SYNC COMPLETE"
    Write-Host "=" * 60
    
} finally {
    Pop-Location
}
