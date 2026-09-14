# Rebuilds the site and pushes it to GitHub Pages if anything changed.
# "Continue": native tools write progress to stderr; failures are detected via exit codes
$ErrorActionPreference = "Continue"
$repo = Split-Path $PSScriptRoot -Parent
$log = Join-Path $PSScriptRoot "sync.log"

function Write-Log($msg) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg" | Out-File $log -Append -Encoding utf8 }

try {
    $env:PYTHONIOENCODING = "utf-8"
    $out = python (Join-Path $PSScriptRoot "build.py") 2>&1
    $code = $LASTEXITCODE
    $out | Out-File $log -Append -Encoding utf8
    if ($code -ne 0) { throw "build.py failed" }

    git -C $repo add -A
    git -C $repo diff --cached --quiet
    if ($LASTEXITCODE -eq 0) { Write-Log "no changes"; exit 0 }

    git -C $repo commit -q -m "Update CV $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    $out = git -C $repo push -q origin main 2>&1
    $code = $LASTEXITCODE
    $out | Out-File $log -Append -Encoding utf8
    if ($code -ne 0) { throw "git push failed" }
    Write-Log "published"
} catch {
    Write-Log "ERROR: $_"
    exit 1
}
