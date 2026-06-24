$ErrorActionPreference = "Continue"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$log = Join-Path $root "backend.local.log"

& (Join-Path $PSScriptRoot "run_backend_local.ps1") *> $log
