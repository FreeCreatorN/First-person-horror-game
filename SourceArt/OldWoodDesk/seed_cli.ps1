$taskCli='D:\UE\Project\HorrorGame\Tools\CLI-Anything\venv\Scripts\cli-anything-blender.exe'
$taskScene='D:\UE\Project\HorrorGame\SourceArt\OldWoodDesk\OldWoodDesk.blend-cli.json'
$env:Path='D:\SteamLibrary\steamapps\common\Blender;'+$env:Path
& $taskCli --json scene new --name OldWoodDesk --engine CYCLES --samples 24 --resolution-x 1000 --resolution-y 800 -o $taskScene | Out-Null
& $taskCli --json --project $taskScene object add cube --name Tabletop --location '0,0,0.752' --scale '0.6,0.32,0.018' | Out-Null
foreach($taskX in @(-.505,.505)) {
    foreach($taskY in @(-.245,.245)) {
        & $taskCli --json --project $taskScene object add cube --name Leg --location "$taskX,$taskY,0.367" --scale '0.0325,0.0325,0.367' | Out-Null
    }
}
& $taskCli --json --project $taskScene camera add --name Camera_Desk --location '1.5,-1.9,1.35' --rotation '70,0,38' --active | Out-Null
& $taskCli --json --project $taskScene camera set 0 clip_start .01 | Out-Null
& $taskCli --json --project $taskScene light add area --name Preview_Key --location '0.5,-1.5,2.6' --rotation '32,0,20' --power 180 | Out-Null
& $taskCli --json --project $taskScene render script 'D:\UE\Project\HorrorGame\SourceArt\OldWoodDesk\Seed.png' | Set-Content -LiteralPath 'D:\UE\Project\HorrorGame\SourceArt\OldWoodDesk\cli_seed.py' -Encoding utf8
& $taskCli --json --project $taskScene preview capture --recipe quick --root-dir 'D:\UE\Project\HorrorGame\SourceArt\OldWoodDesk\CLI_Previews' *> 'D:\UE\Project\HorrorGame\SourceArt\OldWoodDesk\cli_preview_report.json'
