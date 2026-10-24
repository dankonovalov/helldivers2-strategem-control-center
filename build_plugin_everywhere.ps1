$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$releaseDirectory = Join-Path $projectRoot "dist"
$installerName = "com.super-earth.helldivers2.streamDeckPlugin"
$installerPath = Join-Path $releaseDirectory $installerName
$packageDirectory = Join-Path $releaseDirectory "Helldivers2-Stratagems-Portable"
$archivePath = Join-Path $releaseDirectory "Helldivers2-Stratagems-Portable.zip"
$portableLibraryDirectory = Join-Path $packageDirectory "stratagem_library"

Set-Location $projectRoot

# Build the plugin and create the standalone installer in dist\.
& (Join-Path $projectRoot "build_streamdeck_plugin.ps1")
if ($LASTEXITCODE -ne 0) {
    throw "Stream Deck plugin build failed with exit code $LASTEXITCODE"
}

if (-not (Test-Path -LiteralPath $installerPath)) {
    throw "Plugin installer was not created: $installerPath"
}
if (-not (Test-Path -LiteralPath $packageDirectory)) {
    throw "Portable folder does not exist. Run .\build_portable.ps1 once first."
}
if (-not (Test-Path -LiteralPath $portableLibraryDirectory)) {
    throw "Portable stratagem library does not exist: $portableLibraryDirectory"
}

# Keep the plugin installer and the data used by the GUI next to the portable EXE
# synchronized with the source tree.
Copy-Item `
    -LiteralPath $installerPath `
    -Destination (Join-Path $packageDirectory $installerName) `
    -Force
Copy-Item `
    -LiteralPath (Join-Path $projectRoot "stratagem_library\stratagems.json") `
    -Destination (Join-Path $portableLibraryDirectory "stratagems.json") `
    -Force

# Refresh the distributable ZIP as well, otherwise it would still contain the
# previous plugin even though the unpacked portable folder is up to date.
$resolvedProjectRoot = [System.IO.Path]::GetFullPath($projectRoot)
$resolvedPackageDirectory = [System.IO.Path]::GetFullPath($packageDirectory)
$resolvedArchivePath = [System.IO.Path]::GetFullPath($archivePath)
if (-not $resolvedPackageDirectory.StartsWith($resolvedProjectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe package directory: $resolvedPackageDirectory"
}
if (-not $resolvedArchivePath.StartsWith($resolvedProjectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe archive path: $resolvedArchivePath"
}
if (Test-Path -LiteralPath $archivePath) {
    Remove-Item -LiteralPath $archivePath -Force
}
Get-ChildItem -LiteralPath $packageDirectory |
    Compress-Archive -DestinationPath $archivePath -CompressionLevel Optimal

$manifest = Get-Content `
    -LiteralPath (Join-Path $projectRoot "plugin\com.super-earth.helldivers2.sdPlugin\manifest.json") `
    -Raw | ConvertFrom-Json
$installerHash = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash

Write-Host "Plugin version:    $($manifest.Version)"
Write-Host "Plugin installer:  $installerPath"
Write-Host "Portable copy:     $(Join-Path $packageDirectory $installerName)"
Write-Host "Portable ZIP:      $archivePath"
Write-Host "Plugin SHA256:     $installerHash"
