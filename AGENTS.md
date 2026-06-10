# Repository Guidelines

## Project Structure & Module Organization

This is a Windows desktop cleanup tool built with Python and PySide6.

- `main.py` starts the application and requests administrator elevation on Windows.
- `cleaner_app/` contains the product code: UI, scanner, rule catalog, safety guard, executor, and Windows helpers.
- `tests/` contains `unittest` coverage for safety rules, cleanup execution, scanner behavior, and PUP rule coverage.
- `requirements.txt` lists runtime dependencies.

Generated files such as `__pycache__/`, `.test_tmp/`, `.venv/`, `build/`, and `dist/` should stay out of version control.

## Build, Test, and Development Commands

- `python -m venv .venv` creates a local virtual environment.
- `.venv\Scripts\pip install -r requirements.txt` installs PySide6, psutil, and send2trash.
- `python main.py` launches the desktop app. On Windows it attempts administrator elevation.
- `python -m unittest discover -v` runs the full test suite.
- `python -m py_compile main.py cleaner_app\*.py tests\*.py` performs a quick syntax check.

## Coding Style & Naming Conventions

Use Python 3.13-compatible code, 4-space indentation, explicit dataclasses for structured data, and small modules with clear ownership. Use `snake_case` for modules, functions, and variables; `PascalCase` for classes; and descriptive rule ids such as `pup.2345_cache` or `system.user_temp`.

## Testing Guidelines

Use the standard `unittest` framework. Tests must not touch real system junk paths; create simulated files through `tests.helpers.temporary_workspace_dir()`. Any cleanup execution test must inject a fake trash function or use a temporary app data directory. Add regression tests for every safety or deletion behavior change.

## Commit & Pull Request Guidelines

No Git history is available, so use concise imperative commits such as `Add stubborn software scanner` or `Block protected user folders`. Pull requests should include a summary, test output, safety impact, and screenshots for UI changes.

## Safety Requirements

All cleanup execution must pass through `SafetyGuard` and `CleanupExecutor`. Do not delete files permanently by default. High-risk registry, service, startup, process, and scheduled-task findings are inspection-only unless a future change adds explicit, tested recovery and confirmation flows.
