$ErrorActionPreference='Stop'
$setCli='D:\UE\Project\HorrorGame\Tools\CLI-Anything\venv\Scripts\cli-anything-blender.exe'
$setScene='D:\UE\Project\HorrorGame\SourceArt\LightBulb\LightBulb.blend-cli.json'
$env:Path='D:\SteamLibrary\steamapps\common\Blender;'+$env:Path
& $setCli --json scene new --name LightBulb --engine CYCLES --samples 24 --resolution-x 1600 --resolution-y 1000 -o $setScene | Out-Null
if ($LASTEXITCODE -ne 0) {throw 'CLI scene failed'}
& $setCli --json --project $setScene object add cube --name Board --location '-.14,0,.001' --scale '.11,.055,.001' | Out-Null
& $setCli --json --project $setScene object add cube --name Clip --location '.14,0,.002' --scale '.11,.055,.002' | Out-Null
& $setCli --json --project $setScene object add cube --name Paper --location '.14,.015,.006' --scale '.1025,.0475,.000065' | Out-Null
& $setCli --json --project $setScene camera add --name Camera --location '.3,-.48,.55' --rotation '35,0,20' --active | Out-Null
& $setCli --json --project $setScene camera set 0 clip_start .0001 | Out-Null
& $setCli --json --project $setScene light add area --name PreviewKey --location '0,-.2,.6' --rotation '25,0,0' --power 12 | Out-Null
& $setCli --json --project $setScene render script 'D:\UE\Project\HorrorGame\SourceArt\LightBulb\Seed.png' | Set-Content -LiteralPath 'D:\UE\Project\HorrorGame\SourceArt\LightBulb\cli_seed.py' -Encoding utf8
if ($LASTEXITCODE -ne 0) {throw 'CLI script failed'}
& $setCli --json --project $setScene preview capture --recipe quick --root-dir 'D:\UE\Project\HorrorGame\SourceArt\LightBulb\CLI_Previews' *> 'D:\UE\Project\HorrorGame\SourceArt\LightBulb\cli_preview_report.json'
if ($LASTEXITCODE -ne 0) {throw 'CLI preview failed'}



