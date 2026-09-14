# Watches the CV markdown files and the media folder, and publishes changes.
# Started automatically at login by the "CV-sivu" scheduled task.
$config = Get-Content (Join-Path $PSScriptRoot "config.json") -Raw -Encoding utf8 | ConvertFrom-Json
$sync = Join-Path $PSScriptRoot "sync.ps1"

$cvFiles = @($config.cv_files.fi, $config.cv_files.en) | ForEach-Object { [IO.Path]::GetFullPath($_) }
$folders = @($cvFiles | ForEach-Object { Split-Path $_ -Parent }) + @($config.media_folder) | Sort-Object -Unique

$watchers = foreach ($folder in $folders) {
    if (-not (Test-Path $folder)) { continue }
    $w = New-Object IO.FileSystemWatcher $folder
    $w.IncludeSubdirectories = $false
    $w.NotifyFilter = [IO.NotifyFilters]'FileName, LastWrite, Size'
    $w.EnableRaisingEvents = $true
    $w
}

$mediaFolder = [IO.Path]::GetFullPath($config.media_folder)
$pending = $false
$lastEvent = Get-Date

foreach ($w in $watchers) {
    foreach ($evt in "Changed", "Created", "Deleted", "Renamed") {
        Register-ObjectEvent $w $evt -SourceIdentifier "cv-$($w.Path)-$evt" | Out-Null
    }
}

# Publish once at startup so edits made while the computer was off are picked up
& powershell -NoProfile -ExecutionPolicy Bypass -File $sync

while ($true) {
    $e = Wait-Event -Timeout 5
    if ($e) {
        $path = [IO.Path]::GetFullPath($e.SourceEventArgs.FullPath)
        if ($cvFiles -contains $path -or (Split-Path $path -Parent) -eq $mediaFolder) {
            $pending = $true
            $lastEvent = Get-Date
        }
        Remove-Event -EventIdentifier $e.EventIdentifier
        continue
    }
    # wait until files have been quiet for 10 s (editors save in several steps)
    if ($pending -and ((Get-Date) - $lastEvent).TotalSeconds -ge 10) {
        $pending = $false
        & powershell -NoProfile -ExecutionPolicy Bypass -File $sync
    }
}
