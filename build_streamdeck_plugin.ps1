$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pluginName = "com.super-earth.helldivers2.sdPlugin"
$pluginDirectory = Join-Path $projectRoot "plugin\$pluginName"
$binDirectory = Join-Path $pluginDirectory "bin"
$imagesDirectory = Join-Path $pluginDirectory "imgs"
$releaseDirectory = Join-Path $projectRoot "dist"
$workDirectory = Join-Path $projectRoot "build\pyinstaller-streamdeck-plugin"

Set-Location $projectRoot
New-Item -ItemType Directory -Path $binDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $imagesDirectory -Force | Out-Null

py -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --noconsole `
    --icon (Join-Path $projectRoot "app_icon.ico") `
    --name "helldivers-stratagems" `
    --distpath $binDirectory `
    --workpath $workDirectory `
    --specpath (Join-Path $projectRoot "build") `
    (Join-Path $projectRoot "main.py")
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

Copy-Item (Join-Path $projectRoot "config.default.json") (Join-Path $pluginDirectory "config.json") -Force
Copy-Item (Join-Path $projectRoot "stratagems.json") $pluginDirectory -Force
Copy-Item (Join-Path $projectRoot "stratagem_library") $pluginDirectory -Recurse -Force
$stagedLibraryDirectory = Join-Path $pluginDirectory "stratagem_library"
# OpenCV matching and Stream Deck setImage both use PNG. SVG files are source
# assets used to regenerate PNGs and do not need to ship in the plugin.
Get-ChildItem -LiteralPath $stagedLibraryDirectory -Filter "*.svg" -File -Recurse |
    Remove-Item -Force
Copy-Item (Join-Path $projectRoot "stratagem_library\reinforce.png") (Join-Path $imagesDirectory "plugin.png") -Force
Copy-Item (Join-Path $projectRoot "stratagem_library\reinforce.png") (Join-Path $imagesDirectory "plugin@2x.png") -Force
Copy-Item (Join-Path $projectRoot "stratagem_library\reinforce.png") (Join-Path $imagesDirectory "slot.png") -Force
Copy-Item (Join-Path $projectRoot "stratagem_library\reinforce.png") (Join-Path $imagesDirectory "slot@2x.png") -Force
Copy-Item (Join-Path $projectRoot "stratagem_library\reinforce.png") (Join-Path $imagesDirectory "reinforce.png") -Force
Copy-Item (Join-Path $projectRoot "stratagem_library\reinforce.png") (Join-Path $imagesDirectory "reinforce@2x.png") -Force
Copy-Item (Join-Path $projectRoot "stratagem_library\resupply.png") (Join-Path $imagesDirectory "resupply.png") -Force
Copy-Item (Join-Path $projectRoot "stratagem_library\resupply.png") (Join-Path $imagesDirectory "resupply@2x.png") -Force
Copy-Item (Join-Path $projectRoot "stratagem_library\hellbomb.png") (Join-Path $imagesDirectory "hellbomb.png") -Force
Copy-Item (Join-Path $projectRoot "stratagem_library\hellbomb.png") (Join-Path $imagesDirectory "hellbomb@2x.png") -Force

New-Item -ItemType Directory -Path $releaseDirectory -Force | Out-Null
$installerPath = Join-Path $releaseDirectory "com.super-earth.helldivers2.streamDeckPlugin"
npx --yes @elgato/cli pack --force --no-file-list --output $releaseDirectory $pluginDirectory
if ($LASTEXITCODE -ne 0) {
    throw "Elgato CLI pack failed with exit code $LASTEXITCODE"
}

Write-Host "Plugin folder:    $pluginDirectory"
Write-Host "Plugin installer: $installerPath"
