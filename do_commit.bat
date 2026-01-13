@echo off
setlocal enabledelayedexpansion

cd /d "c:\Users\aerki\riven\trc"

REM Configure git to avoid pagers
set GIT_EDITOR=cmd /c exit
set GIT_PAGER=cmd /c exit

REM Stage all changes
echo Staging changes...
git add -A
if errorlevel 1 (
    echo Error: git add failed
    exit /b 1
)

REM Commit using the prepared message file
echo Committing changes...
git commit -F .git\COMMIT_MSG --no-verify
if errorlevel 1 (
    echo Error: git commit failed
    exit /b 1
)

REM Show the commit
echo.
echo Commit successful! Latest commits:
git log --oneline -3

echo.
echo Done. You can now push with: git push origin main
