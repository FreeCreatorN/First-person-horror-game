$taskCli='D:\UE\Project\HorrorGame\Tools\CLI-Anything\venv\Scripts\cli-anything-blender.exe'
$taskScene='D:\UE\Project\HorrorGame\SourceArt\AltarTable\AltarTable.blend-cli.json'
$env:Path='D:\SteamLibrary\steamapps\common\Blender;'+$env:Path
& $taskCli --json scene new --name AltarTable --engine CYCLES --samples 24 --resolution-x 1200 --resolution-y 800 -o $taskScene | Out-Null
& $taskCli --json --project $taskScene object add cube --name LongTabletop --location '0,0,0.928' --scale '1.1,0.3,0.022' | Out-Null
foreach($taskX in @(-.90,.90)) {
    foreach($taskY in @(-.215,.215)) {
        & $taskCli --json --project $taskScene object add cube --name SquareLeg --location "$taskX,$taskY,0.455" --scale '0.038,0.038,0.455' | Out-Null
    }
}
& $taskCli --json --project $taskScene object add cube --name FrontApron --location '0,-0.226,0.82' --scale '0.94,0.016,0.085' | Out-Null
& $taskCli --json --project $taskScene camera add --name Camera_Altar --location '2.8,-3.1,1.8' --rotation '73,0,42' --active | Out-Null
& $taskCli --json --project $taskScene camera set 0 clip_start .01 | Out-Null
& $taskCli --json --project $taskScene light add area --name Preview_Key --location '0.7,-2,3' --rotation '35,0,15' --power 250 | Out-Null
& $taskCli --json --project $taskScene render script 'D:\UE\Project\HorrorGame\SourceArt\AltarTable\Seed.png' | Set-Content -LiteralPath 'D:\UE\Project\HorrorGame\SourceArt\AltarTable\cli_seed.py' -Encoding utf8
& $taskCli --json --project $taskScene preview capture --recipe quick --root-dir 'D:\UE\Project\HorrorGame\SourceArt\AltarTable\CLI_Previews' *> 'D:\UE\Project\HorrorGame\SourceArt\AltarTable\cli_preview_report.json'
