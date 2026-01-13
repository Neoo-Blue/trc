# Start a fresh cmd process that runs the commit
$processInfo = New-Object System.Diagnostics.ProcessStartInfo
$processInfo.FileName = "cmd.exe"
$processInfo.Arguments = "/c cd c:\Users\aerki\riven\trc && set GIT_EDITOR=cmd /c exit && set GIT_PAGER=cmd /c exit && git add -A && git commit -F .git\COMMIT_MSG --no-verify && git log --oneline -1"
$processInfo.UseShellExecute = $false
$processInfo.RedirectStandardOutput = $true
$processInfo.RedirectStandardError = $true
$processInfo.CreateNoWindow = $true

$process = [System.Diagnostics.Process]::Start($processInfo)
$output = $process.StandardOutput.ReadToEnd()
$error = $process.StandardError.ReadToEnd()
$process.WaitForExit()

Write-Host "=== COMMIT OUTPUT ===" 
Write-Host $output
if ($error) {
    Write-Host "=== ERRORS ===" 
    Write-Host $error
}
Write-Host "Exit code: $($process.ExitCode)"
