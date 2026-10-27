$ErrorActionPreference='Stop'
$photoCli='D:\UE\Project\HorrorGame\Tools\CLI-Anything\venv\Scripts\cli-anything-blender.exe'
$photoRoot='D:\UE\Project\HorrorGame\SourceArt\PhotoPaper'
$photoScene=Join-Path $photoRoot 'PhotoPaper.blend-cli.json'
$env:Path='D:\SteamLibrary\steamapps\common\Blender;'+$env:Path
function Invoke-PhotoCli { & $photoCli @args; if($LASTEXITCODE -ne 0){throw 'Photo paper CLI step failed'} }
Invoke-PhotoCli --json scene new --name PhotoPaper --engine CYCLES --samples 24 --resolution-x 1400 --resolution-y 1200 -o $photoScene | Out-Null
Invoke-PhotoCli --json --project $photoScene object add cube --name Paper --location '0,0,.000175' --scale '.044,.054,.000175' | Out-Null
Invoke-PhotoCli --json --project $photoScene object add cube --name ImageRegion --location '0,.010,.00036' --scale '.039,.039,.00001' | Out-Null
Invoke-PhotoCli --json --project $photoScene camera add --name Camera --location '.14,-.18,.23' --rotation '45,0,38' --active | Out-Null
Invoke-PhotoCli --json --project $photoScene camera set 0 clip_start .00001 | Out-Null
Invoke-PhotoCli --json --project $photoScene light add area --name PreviewKey --location '-.12,-.12,.26' --rotation '30,0,0' --power 3 | Out-Null
Invoke-PhotoCli --json --project $photoScene render script (Join-Path $photoRoot 'Seed.png') | Set-Content -LiteralPath (Join-Path $photoRoot 'cli_seed.py') -Encoding utf8
Invoke-PhotoCli --json --project $photoScene preview capture --recipe quick --root-dir (Join-Path $photoRoot 'CLI_Previews') *> (Join-Path $photoRoot 'cli_preview_report.json')
