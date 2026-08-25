$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot ".build-venv\Scripts\python.exe"
$releaseDir = Join-Path $projectRoot "release\Open-Nuclear-Engineering-Teaching-Suite-2.0.0-Windows"
$workDir = Join-Path $projectRoot "build"
$specDir = Join-Path $projectRoot "build-specs"
$env:QT_API = "pyside6"

if (-not (Test-Path -LiteralPath $python)) {
    py -m venv --system-site-packages (Join-Path $projectRoot ".build-venv")
}

& $python -m pip install --upgrade pyinstaller
& $python -m pip install -r (Join-Path $projectRoot "requirements.txt")
& $python -m pip install -r (Join-Path $projectRoot "simulators\HardwareReactorControlPanel\requirements-hardware.txt")

New-Item -ItemType Directory -Force -Path $releaseDir, $workDir, $specDir | Out-Null

$commonArgs = @(
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--distpath", $releaseDir,
    "--workpath", $workDir,
    "--specpath", $specDir
)

& $python -m PyInstaller @commonArgs `
    --name "Reactor-Physics-and-Kinetics-Simulator" `
    --paths "$projectRoot\simulators\ReactorPhysicsSimulator" `
    --exclude-module pandas --exclude-module scipy --exclude-module pyarrow --exclude-module PyQt5 `
    "$projectRoot\simulators\ReactorPhysicsSimulator\main.py"

& $python -m PyInstaller @commonArgs `
    --name "Thermal-Hydraulics-and-LOCA-Simulator" `
    --paths "$projectRoot\simulators\ThermalHydraulicsSimulator" `
    --add-data "$projectRoot\simulators\ThermalHydraulicsSimulator\data\if97_ph_table.npz;data" `
    --exclude-module pandas --exclude-module scipy --exclude-module pyarrow --exclude-module PyQt5 `
    "$projectRoot\simulators\ThermalHydraulicsSimulator\main.py"

& $python -m PyInstaller @commonArgs `
    --name "Core-Loading-Simulator" `
    --paths "$projectRoot\simulators\CoreLoadingSimulator" `
    --exclude-module pandas `
    "$projectRoot\simulators\CoreLoadingSimulator\main.py"

& $python -m PyInstaller @commonArgs `
    --name "Hardware-Reactor-Control-Panel-UNTESTED" `
    --paths "$projectRoot\simulators\HardwareReactorControlPanel" `
    --paths "$projectRoot\simulators\ReactorPhysicsSimulator" `
    --hidden-import serial --hidden-import serial.tools.list_ports `
    --exclude-module pandas --exclude-module scipy --exclude-module pyarrow --exclude-module PyQt5 `
    "$projectRoot\simulators\HardwareReactorControlPanel\main.py"

Copy-Item -LiteralPath "$projectRoot\WINDOWS-README.TXT" `
    -Destination (Join-Path $releaseDir "README.TXT") -Force
Copy-Item -LiteralPath "$projectRoot\LICENSE" -Destination $releaseDir -Force
Copy-Item -LiteralPath "$projectRoot\CITATION.cff" -Destination $releaseDir -Force
Copy-Item -LiteralPath "$projectRoot\VERSION" -Destination $releaseDir -Force

Get-FileHash -Algorithm SHA256 `
    (Join-Path $releaseDir "Reactor-Physics-and-Kinetics-Simulator.exe"), `
    (Join-Path $releaseDir "Thermal-Hydraulics-and-LOCA-Simulator.exe"), `
    (Join-Path $releaseDir "Core-Loading-Simulator.exe"), `
    (Join-Path $releaseDir "Hardware-Reactor-Control-Panel-UNTESTED.exe") |
    ForEach-Object { "$($_.Hash)  $(Split-Path -Leaf $_.Path)" } |
    Set-Content -Encoding ascii (Join-Path $releaseDir "SHA256SUMS.txt")

$zipPath = "$releaseDir.zip"
Compress-Archive -Path (Join-Path $releaseDir "*") -DestinationPath $zipPath -Force

Write-Host "Standalone release created at:"
Write-Host $releaseDir
Write-Host $zipPath
