$ErrorActionPreference='Stop'
$diningCli='D:\UE\Project\HorrorGame\Tools\CLI-Anything\venv\Scripts\cli-anything-blender.exe'
$diningScene='D:\UE\Project\HorrorGame\SourceArt\LargeDiningTable\LargeDiningTable.blend-cli.json'
$env:Path='D:\SteamLibrary\steamapps\common\Blender;'+$env:Path
& $diningCli --json scene new --name LargeDiningTable --engine CYCLES --samples 24 --resolution-x 1200 --resolution-y 800 -o $diningScene | Out-Null
if ($LASTEXITCODE -ne 0) {throw 'CLI scene creation failed'}
& $diningCli --json --project $diningScene object add cube --name LongDiningTop --location '0,0,0.738' --scale '1.2,0.525,0.022' | Out-Null
foreach ($diningX in @(-.995,.995)) {
 foreach ($diningY in @(-.375,.375)) {
  & $diningCli --json --project $diningScene object add cube --name DiningLeg --location "$diningX,$diningY,0.36" --scale '.05,.05,.36' | Out-Null
  if ($LASTEXITCODE -ne 0) {throw 'CLI leg creation failed'}
 }
}
& $diningCli --json --project $diningScene camera add --name DiningCamera --location '3.1,-3.5,2.4' --rotation '65,0,40' --active | Out-Null
& $diningCli --json --project $diningScene camera set 0 clip_start .01 | Out-Null
& $diningCli --json --project $diningScene light add area --name PreviewKey --location '0,-2,3' --rotation '30,0,0' --power 400 | Out-Null
& $diningCli --json --project $diningScene render script 'D:\UE\Project\HorrorGame\SourceArt\LargeDiningTable\Seed.png' | Set-Content -LiteralPath 'D:\UE\Project\HorrorGame\SourceArt\LargeDiningTable\cli_seed.py' -Encoding utf8
if ($LASTEXITCODE -ne 0) {throw 'CLI build script failed'}
& $diningCli --json --project $diningScene preview capture --recipe quick --root-dir 'D:\UE\Project\HorrorGame\SourceArt\LargeDiningTable\CLI_Previews' *> 'D:\UE\Project\HorrorGame\SourceArt\LargeDiningTable\cli_preview_report.json'
if ($LASTEXITCODE -ne 0) {throw 'CLI preview failed'}
