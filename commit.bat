@echo off
cd /d c:\Users\aerki\riven\trc
git add -A
git commit -m "Enforce state filtering: only process Failed/Unknown items

- Enhanced get_problem_items() fallback to filter locally by state
- Added state re-validation in _handle_problem_item()
- Items with changed states automatically removed from tracking
- Added STATE_FILTERING.md documentation
- Created verify_states.py verification script

This ensures TRC only processes items in Failed or Unknown states from Riven,
with multiple layers of filtering and validation."
echo.
echo Commit complete. Status:
git log --oneline -1
echo.
pause
