$ErrorActionPreference = "Continue"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$log = Join-Path $root "frontend.local.log"

& (Join-Path $PSScriptRoot "run_frontend_local.ps1") *> $log
