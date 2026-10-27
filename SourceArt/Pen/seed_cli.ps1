$ErrorActionPreference='Stop'
$penCli='D:\UE\Project\HorrorGame\Tools\CLI-Anything\venv\Scripts\cli-anything-blender.exe'
$penRoot='D:\UE\Project\HorrorGame\SourceArt\Pen'
$penScene=Join-Path $penRoot 'Pen.blend-cli.json'
$env:Path='D:\SteamLibrary\steamapps\common\Blender;'+$env:Path
function Invoke-PenCli { & $penCli @args; if($LASTEXITCODE -ne 0){throw 'Pen CLI step failed'} }
Invoke-PenCli --json scene new --name Pen --engine CYCLES --samples 24 --resolution-x 1400 --resolution-y 1000 -o $penScene | Out-Null
Invoke-PenCli --json --project $penScene object add cylinder --name Barrel --location '0,0,.057' --scale '.0053,.0053,.038' | Out-Null
Invoke-PenCli --json --project $penScene object add cylinder --name MetalCap --location '0,0,.113' --scale '.0053,.0053,.018' | Out-Null
Invoke-PenCli --json --project $penScene object add cylinder --name ClickButton --location '0,0,.137' --scale '.0033,.0033,.005' | Out-Null
Invoke-PenCli --json --project $penScene object add cube --name Clip --location '0,-.007,.110' --scale '.0014,.0003,.018' | Out-Null
Invoke-PenCli --json --project $penScene camera add --name Camera --location '.20,-.30,.18' --rotation '73,0,34' --active | Out-Null
Invoke-PenCli --json --project $penScene camera set 0 clip_start .0001 | Out-Null
Invoke-PenCli --json --project $penScene light add area --name PreviewKey --location '.05,-.15,.24' --rotation '30,0,0' --power 4 | Out-Null
Invoke-PenCli --json --project $penScene render script (Join-Path $penRoot 'Seed.png') | Set-Content -LiteralPath (Join-Path $penRoot 'cli_seed.py') -Encoding utf8
Invoke-PenCli --json --project $penScene preview capture --recipe quick --root-dir (Join-Path $penRoot 'CLI_Previews') *> (Join-Path $penRoot 'cli_preview_report.json')
