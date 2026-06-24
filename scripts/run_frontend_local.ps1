$ErrorActionPreference = "Continue"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location (Join-Path $root "frontend")

$env:VITE_API_BASE_URL = "http://localhost:8000"
$env:VITE_USE_MOCK = "false"

npm run dev -- --host 0.0.0.0
