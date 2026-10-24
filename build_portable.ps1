param(
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$releaseRoot = Join-Path $projectRoot "dist"
$packageName = "Helldivers2-Stratagems-Portable"
$packageDirectory = Join-Path $releaseRoot $packageName
$archivePath = Join-Path $releaseRoot "$packageName.zip"
$guiBuildDirectory = Join-Path $projectRoot "build\pyinstaller-gui"
$guiDistDirectory = Join-Path $projectRoot "build\gui-dist"
$guiAppDirectory = Join-Path $guiDistDirectory "Helldivers2-Stratagems-Control"

Set-Location $projectRoot

if (-not $SkipBuild) {
    py -m PyInstaller `
        --noconfirm `
        --clean `
        --onedir `
        --windowed `
        --icon (Join-Path $projectRoot "app_icon.ico") `
        --add-data "$projectRoot\locales;locales" `
        --name "Helldivers2-Stratagems-Control" `
        --distpath $guiDistDirectory `
        --workpath $guiBuildDirectory `
        --specpath (Join-Path $projectRoot "build") `
        (Join-Path $projectRoot "app_ui.py")
    if ($LASTEXITCODE -ne 0) {
        throw "GUI PyInstaller build failed with exit code $LASTEXITCODE"
    }

    & (Join-Path $projectRoot "build_streamdeck_plugin.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "Stream Deck plugin build failed with exit code $LASTEXITCODE"
    }
}

New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null

$resolvedProjectRoot = [System.IO.Path]::GetFullPath($projectRoot)
$resolvedPackageDirectory = [System.IO.Path]::GetFullPath($packageDirectory)
if (-not $resolvedPackageDirectory.StartsWith($resolvedProjectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe package directory: $resolvedPackageDirectory"
}
if (Test-Path -LiteralPath $packageDirectory) {
    Remove-Item -LiteralPath $packageDirectory -Recurse -Force
}
if (Test-Path -LiteralPath $archivePath) {
    Remove-Item -LiteralPath $archivePath -Force
}

New-Item -ItemType Directory -Path $packageDirectory -Force | Out-Null
Copy-Item (Join-Path $guiAppDirectory "*") $packageDirectory -Recurse -Force
# PyInstaller's PyQt6 hook keeps Qt runtime DLLs under PyQt6\Qt6\bin, but
# Python 3.14 can resolve an incompatible DLL first in a frozen process. The
# _internal directory is prepended to PATH by the bootloader, so mirror the
# Qt DLLs there to make dependency resolution deterministic.
$internalDirectory = Join-Path $packageDirectory "_internal"
$qtBinDirectory = Join-Path $internalDirectory "PyQt6\Qt6\bin"
Copy-Item (Join-Path $qtBinDirectory "*.dll") $internalDirectory -Force
# The Codex build environment puts Poppler's ICU 78 DLLs on PATH. PyInstaller
# may collect them as Qt6Core dependencies, but PyQt6 on Windows uses the
# operating system ICU. Bundling Poppler's copies shadows System32 and makes
# QtCore fail with ERROR_PROC_NOT_FOUND at startup.
foreach ($conflictingIcuDll in @("icuuc.dll", "icudt78.dll")) {
    $conflictingIcuPath = Join-Path $internalDirectory $conflictingIcuDll
    if (Test-Path -LiteralPath $conflictingIcuPath) {
        Remove-Item -LiteralPath $conflictingIcuPath -Force
    }
}
# Qt DLLs are copied to _internal above so the Windows loader finds the correct
# versions before incompatible DLLs from PATH. Keeping identical copies in the
# original Qt bin directory only makes the portable archive larger.
Get-ChildItem -LiteralPath $qtBinDirectory -Filter "*.dll" -File | ForEach-Object {
    $rootQtDll = Join-Path $internalDirectory $_.Name
    if (
        (Test-Path -LiteralPath $rootQtDll) -and
        ((Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash -eq
            (Get-FileHash -LiteralPath $rootQtDll -Algorithm SHA256).Hash)
    ) {
        Remove-Item -LiteralPath $_.FullName -Force
    }
}
Copy-Item (Join-Path $projectRoot "config.default.json") (Join-Path $packageDirectory "config.json")
Copy-Item (Join-Path $projectRoot "app_icon.ico") $packageDirectory
Copy-Item (Join-Path $projectRoot "locales") $packageDirectory -Recurse
Copy-Item (Join-Path $projectRoot "stratagem_library") $packageDirectory -Recurse
$portableLibraryDirectory = Join-Path $packageDirectory "stratagem_library"
Get-ChildItem -LiteralPath $portableLibraryDirectory -Filter "*.svg" -File -Recurse |
    Remove-Item -Force
Copy-Item (Join-Path $releaseRoot "com.super-earth.helldivers2.streamDeckPlugin") $packageDirectory
Copy-Item (Join-Path $projectRoot "PORTABLE_README_UA.txt") (Join-Path $packageDirectory "README.txt")

Get-ChildItem -LiteralPath $packageDirectory |
    Compress-Archive -DestinationPath $archivePath -CompressionLevel Optimal

Write-Host "Portable folder: $packageDirectory"
Write-Host "Portable ZIP:    $archivePath"
