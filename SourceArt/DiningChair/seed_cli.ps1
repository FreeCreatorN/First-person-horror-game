$ErrorActionPreference='Stop'
$chairCli='D:\UE\Project\HorrorGame\Tools\CLI-Anything\venv\Scripts\cli-anything-blender.exe'
$chairScene='D:\UE\Project\HorrorGame\SourceArt\DiningChair\DiningChair.blend-cli.json'
$env:Path='D:\SteamLibrary\steamapps\common\Blender;'+$env:Path
& $chairCli --json scene new --name DiningChair --engine CYCLES --samples 24 --resolution-x 1000 --resolution-y 1100 -o $chairScene | Out-Null
if ($LASTEXITCODE -ne 0) {throw 'CLI scene creation failed'}
& $chairCli --json --project $chairScene object add cube --name HardwoodSeat --location '0,-.02,.4425' --scale '.24,.22,.0175' | Out-Null
foreach ($chairX in @(-.194,.194)) {
 & $chairCli --json --project $chairScene object add cube --name FrontLeg --location "$chairX,-.188,.22" --scale '.025,.025,.22' | Out-Null
 & $chairCli --json --project $chairScene object add cube --name RearBackPost --location "$chairX,.21,.52" --scale '.024,.024,.52' | Out-Null
 if ($LASTEXITCODE -ne 0) {throw 'CLI leg creation failed'}
}
& $chairCli --json --project $chairScene object add cube --name CrestRail --location '0,.265,1.025' --scale '.235,.02,.035' | Out-Null
& $chairCli --json --project $chairScene camera add --name ChairCamera --location '1.5,-2,1.35' --rotation '75,0,35' --active | Out-Null
& $chairCli --json --project $chairScene camera set 0 clip_start .005 | Out-Null
& $chairCli --json --project $chairScene light add area --name PreviewKey --location '0,-2,3' --rotation '30,0,0' --power 300 | Out-Null
& $chairCli --json --project $chairScene render script 'D:\UE\Project\HorrorGame\SourceArt\DiningChair\Seed.png' | Set-Content -LiteralPath 'D:\UE\Project\HorrorGame\SourceArt\DiningChair\cli_seed.py' -Encoding utf8
if ($LASTEXITCODE -ne 0) {throw 'CLI build script failed'}
& $chairCli --json --project $chairScene preview capture --recipe quick --root-dir 'D:\UE\Project\HorrorGame\SourceArt\DiningChair\CLI_Previews' *> 'D:\UE\Project\HorrorGame\SourceArt\DiningChair\cli_preview_report.json'
if ($LASTEXITCODE -ne 0) {throw 'CLI preview failed'}
