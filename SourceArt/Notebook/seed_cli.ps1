$ErrorActionPreference='Stop'
$notebookCli='D:\UE\Project\HorrorGame\Tools\CLI-Anything\venv\Scripts\cli-anything-blender.exe'
$notebookRoot='D:\UE\Project\HorrorGame\SourceArt\Notebook'
$notebookScene=Join-Path $notebookRoot 'Notebook.blend-cli.json'
$env:Path='D:\SteamLibrary\steamapps\common\Blender;'+$env:Path
function Invoke-NotebookCli { & $notebookCli @args; if($LASTEXITCODE -ne 0){throw 'Notebook CLI step failed'} }
Invoke-NotebookCli --json scene new --name Notebook --engine CYCLES --samples 24 --resolution-x 1500 --resolution-y 1200 -o $notebookScene | Out-Null
Invoke-NotebookCli --json --project $notebookScene object add cube --name NotebookVolume --location '.073,0,.006' --scale '.077,.111,.006' | Out-Null
Invoke-NotebookCli --json --project $notebookScene camera add --name Camera --location '.30,-.34,.43' --rotation '38,0,38' --active | Out-Null
Invoke-NotebookCli --json --project $notebookScene light add area --name PreviewKey --location '-.12,-.12,.35' --rotation '20,0,0' --power 8 | Out-Null
Invoke-NotebookCli --json --project $notebookScene render script (Join-Path $notebookRoot 'Seed.png') | Set-Content -LiteralPath (Join-Path $notebookRoot 'cli_seed.py') -Encoding utf8
Invoke-NotebookCli --json --project $notebookScene preview capture --recipe quick --root-dir (Join-Path $notebookRoot 'CLI_Previews') *> (Join-Path $notebookRoot 'cli_preview_report.json')
