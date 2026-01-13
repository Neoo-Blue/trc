@echo off
REM Disable git editor and commit directly
cd /d c:\Users\aerki\riven\trc
set GIT_EDITOR=true
set GIT_PAGER=cat
git.exe config core.editor true
git.exe add -A
git.exe commit --quiet -m "Enforce state filtering: only process Failed/Unknown items - Enhanced get_problem_items() fallback to filter locally by state - Added state re-validation in _handle_problem_item() - Items with changed states automatically removed from tracking - Added STATE_FILTERING.md documentation - Created verify_states.py verification script - This ensures TRC only processes items in Failed or Unknown states from Riven"
if errorlevel 1 (
    echo Commit error (may already be committed)
) else (
    echo Commit successful
)
git.exe log --oneline -1
