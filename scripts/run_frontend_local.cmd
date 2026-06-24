@echo off
set ROOT=%~dp0..
cd /d "%ROOT%\frontend"

set VITE_API_BASE_URL=http://localhost:8000
set VITE_USE_MOCK=false

npm run dev -- --host 0.0.0.0 > "%ROOT%\frontend.local.log" 2>&1
