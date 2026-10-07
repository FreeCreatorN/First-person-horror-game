$taskCli='D:\UE\Project\HorrorGame\Tools\CLI-Anything\venv\Scripts\cli-anything-blender.exe'
$taskScene='D:\UE\Project\HorrorGame\SourceArt\Flashlight\Flashlight.blend-cli.json'
$env:Path='D:\SteamLibrary\steamapps\common\Blender;'+$env:Path
& $taskCli --json scene new --name Flashlight --engine CYCLES --samples 24 --resolution-x 1000 --resolution-y 800 -o $taskScene | Out-Null
& $taskCli --json --project $taskScene object add cylinder --name Body --location '-0.01,0,0' --rotation '0,90,0' --param 'radius=0.015' --param 'depth=0.12' | Out-Null
& $taskCli --json --project $taskScene object add cylinder --name Head --location '0.07,0,0' --rotation '0,90,0' --param 'radius=0.025' --param 'depth=0.04' | Out-Null
& $taskCli --json --project $taskScene material create --name M_Flashlight_Anodized --color '0.026,0.036,0.045,1' --metallic .8 --roughness .31 | Out-Null
& $taskCli --json --project $taskScene material assign 0 0 | Out-Null
& $taskCli --json --project $taskScene material assign 0 1 | Out-Null
& $taskCli --json --project $taskScene camera add --name Camera_Flashlight --location '0.25,-0.34,0.23' --rotation '63,0,38' --active | Out-Null
& $taskCli --json --project $taskScene camera set 0 clip_start .001 | Out-Null
& $taskCli --json --project $taskScene light add area --name Studio_Key --location '0.14,-0.18,0.28' --rotation '35,0,30' --power 15 | Out-Null
& $taskCli --json --project $taskScene render script 'D:\UE\Project\HorrorGame\SourceArt\Flashlight\Seed.png' | Set-Content -LiteralPath 'D:\UE\Project\HorrorGame\SourceArt\Flashlight\cli_seed.py' -Encoding utf8
& $taskCli --json --project $taskScene preview capture --recipe quick --root-dir 'D:\UE\Project\HorrorGame\SourceArt\Flashlight\CLI_Previews' *> 'D:\UE\Project\HorrorGame\SourceArt\Flashlight\cli_preview_report.json'
