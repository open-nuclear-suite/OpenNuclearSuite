$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot ".build-venv\Scripts\python.exe"
$releaseDir = Join-Path $projectRoot "release\Open-Nuclear-Engineering-Teaching-Suite-1.2.0-Windows"
$workDir = Join-Path $projectRoot "build"
$specDir = Join-Path $projectRoot "build-specs"

if (-not (Test-Path -LiteralPath $python)) {
    py -m venv --system-site-packages (Join-Path $projectRoot ".build-venv")
}

& $python -m pip install --upgrade pyinstaller
& $python -m pip install -r (Join-Path $projectRoot "requirements.txt")

New-Item -ItemType Directory -Force -Path $releaseDir, $workDir, $specDir | Out-Null

$commonArgs = @(
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--distpath", $releaseDir,
    "--workpath", $workDir,
    "--specpath", $specDir,
    "--add-data", "$projectRoot\assets\UTM.logo.png;.",
    "--add-data", "$projectRoot\utm.fkt.logo.png;."
)

& $python -m PyInstaller @commonArgs `
    --name "Reactor-Physics-and-Kinetics-Simulator" `
    --paths "$projectRoot\simulators\ReactorPhysicsSimulator" `
    "$projectRoot\simulators\ReactorPhysicsSimulator\main.py"

& $python -m PyInstaller @commonArgs `
    --name "Thermal-Hydraulics-and-LOCA-Simulator" `
    --paths "$projectRoot\simulators\ThermalHydraulicsSimulator" `
    "$projectRoot\simulators\ThermalHydraulicsSimulator\main.py"

& $python -m PyInstaller @commonArgs `
    --name "Core-Loading-Simulator" `
    --paths "$projectRoot\simulators\CoreLoadingSimulator" `
    --exclude-module pandas `
    "$projectRoot\simulators\CoreLoadingSimulator\main.py"

Copy-Item -LiteralPath "$projectRoot\WINDOWS-README.TXT" `
    -Destination (Join-Path $releaseDir "README.TXT") -Force
Copy-Item -LiteralPath "$projectRoot\LICENSE" -Destination $releaseDir -Force
Copy-Item -LiteralPath "$projectRoot\CITATION.cff" -Destination $releaseDir -Force

Get-FileHash -Algorithm SHA256 `
    (Join-Path $releaseDir "Reactor-Physics-and-Kinetics-Simulator.exe"), `
    (Join-Path $releaseDir "Thermal-Hydraulics-and-LOCA-Simulator.exe"), `
    (Join-Path $releaseDir "Core-Loading-Simulator.exe") |
    ForEach-Object { "$($_.Hash)  $(Split-Path -Leaf $_.Path)" } |
    Set-Content -Encoding ascii (Join-Path $releaseDir "SHA256SUMS.txt")

$zipPath = "$releaseDir.zip"
Compress-Archive -Path (Join-Path $releaseDir "*") -DestinationPath $zipPath -Force

Write-Host "Standalone release created at:"
Write-Host $releaseDir
Write-Host $zipPath
