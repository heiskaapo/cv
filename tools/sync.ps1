# Rebuilds the site and pushes it to GitHub Pages if anything changed.
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$log = Join-Path $PSScriptRoot "sync.log"

function Write-Log($msg) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg" | Out-File $log -Append -Encoding utf8 }

try {
    python (Join-Path $PSScriptRoot "build.py") *>> $log
    if ($LASTEXITCODE -ne 0) { throw "build.py failed" }

    git -C $repo add -A
    git -C $repo diff --cached --quiet
    if ($LASTEXITCODE -eq 0) { Write-Log "no changes"; exit 0 }

    git -C $repo commit -q -m "Update CV $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    git -C $repo push -q origin main *>> $log
    if ($LASTEXITCODE -ne 0) { throw "git push failed" }
    Write-Log "published"
} catch {
    Write-Log "ERROR: $_"
    exit 1
}
