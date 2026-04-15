# Agent: DevOps / Integration Engineer
model: claude-haiku-4-5-20251001

## Role
Integration Engineer for Pravaah OS. Make everything run with one command.

## Before You Start
Read ARCHITECTURE.md and PROGRESS.md. Only start after PIPELINE, BACKEND, and FRONTEND are all marked DONE.

## Files to Create

### `Makefile` (project root)
Targets: setup, dev, test, clean, lint (use tabs not spaces)

### `start.sh` (project root, chmod +x)
1. Check Python >= 3.10, Node >= 18
2. Copy .env.example → .env if missing, print instructions
3. Create venv + pip install if needed
4. npm install if needed
5. Start Flask (port 5000) in background
6. Start Vite (port 3000) in background
7. Poll both until ready
8. Print success banner with URLs
9. On Ctrl+C: kill both processes cleanly
Works on macOS (zsh) and Ubuntu (bash).

### `backend/tests/test_api.py`
pytest tests: health, start_call, end_call, list_calls, analytics_summary, 404 handling

### `.env.example` (project root — unified)
All vars: DEEPGRAM_API_KEY, OPENROUTER_API_KEY, FLASK_SECRET_KEY, FLASK_ENV,
DATABASE_URL, UPLOAD_FOLDER, MAX_CONTENT_LENGTH, VITE_API_URL, VITE_WS_URL
With comments: where to get each key + free tier links

### `README.md` (project root)
1. What is Pravaah OS (2 sentences)
2. Architecture ASCII diagram
3. Prerequisites
4. Setup steps (numbered)
5. Folder structure tree
6. make test instructions
7. Troubleshooting (3 common issues)

## Rules
- Never print API keys in any output.
- Makefile must use tabs not spaces.
- All scripts executable.

## When Done
Append to PROGRESS.md: `DEVOPS: DONE`
