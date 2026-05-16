# Apply 001_initial_schema.sql to Postgres (Supabase SQL editor or local psql)
param(
    [Parameter(Mandatory = $true)]
    [string]$DatabaseUrl
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$sql  = Join-Path $root "migrations\001_initial_schema.sql"

if (-not (Get-Command psql -ErrorAction SilentlyContinue)) {
    Write-Error "psql not found. Paste migrations/001_initial_schema.sql into the Supabase SQL editor instead."
}

$env:PGPASSWORD = ""
& psql $DatabaseUrl -f $sql
Write-Host "Migration applied."
