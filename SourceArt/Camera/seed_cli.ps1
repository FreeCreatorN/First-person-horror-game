$ErrorActionPreference='Stop'
$cameraCli='D:\UE\Project\HorrorGame\Tools\CLI-Anything\venv\Scripts\cli-anything-blender.exe'
$cameraRoot='D:\UE\Project\HorrorGame\SourceArt\Camera'
$cameraScene=Join-Path $cameraRoot 'Camera.blend-cli.json'
$env:Path='D:\SteamLibrary\steamapps\common\Blender;'+$env:Path
function Invoke-CameraCli { & $cameraCli @args; if($LASTEXITCODE -ne 0){throw 'Camera CLI step failed'} }
Invoke-CameraCli --json scene new --name Camera --engine CYCLES --samples 24 --resolution-x 1500 --resolution-y 1100 -o $cameraScene | Out-Null
Invoke-CameraCli --json --project $cameraScene object add cube --name Body --location '0,0,.039' --scale '.071,.024,.036' | Out-Null
Invoke-CameraCli --json --project $cameraScene object add cylinder --name Lens --location '-.008,-.05,.044' --rotation '90,0,0' --scale '.029,.029,.027' | Out-Null
Invoke-CameraCli --json --project $cameraScene object add cube --name Prism --location '-.008,0,.084' --scale '.028,.020,.013' | Out-Null
Invoke-CameraCli --json --project $cameraScene camera add --name Camera --location '.23,-.34,.24' --rotation '64,0,34' --active | Out-Null
Invoke-CameraCli --json --project $cameraScene camera set 0 clip_start .0001 | Out-Null
Invoke-CameraCli --json --project $cameraScene light add area --name PreviewKey --location '-.14,-.16,.30' --rotation '30,0,0' --power 8 | Out-Null
Invoke-CameraCli --json --project $cameraScene render script (Join-Path $cameraRoot 'Seed.png') | Set-Content -LiteralPath (Join-Path $cameraRoot 'cli_seed.py') -Encoding utf8
Invoke-CameraCli --json --project $cameraScene preview capture --recipe quick --root-dir (Join-Path $cameraRoot 'CLI_Previews') *> (Join-Path $cameraRoot 'cli_preview_report.json')
