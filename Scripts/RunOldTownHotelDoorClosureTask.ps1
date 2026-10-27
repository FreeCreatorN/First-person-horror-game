param(
 [Parameter(Mandatory=$true)][string]$Script,
 [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9_-]+$')][string]$LogName,
 [switch]$EnableCopyTools
)
$ErrorActionPreference='Stop'
$taskRoot='D:\UE\Project\HorrorGame'
$taskWork=Join-Path $taskRoot 'Saved\CodexOutputs\OldTownHotelDoorClosure_20261019'
$taskScript=(Resolve-Path -LiteralPath $Script).Path
if (-not $taskScript.StartsWith((Join-Path $taskRoot 'Scripts\'),[StringComparison]::OrdinalIgnoreCase)) {throw 'Script escaped project Scripts'}
if (@(Get-Process -Name UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {throw 'UE editor/helper must be closed'}
New-Item -ItemType Directory -Path $taskWork -Force | Out-Null
$oldCache=[Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
try {
 [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',(Join-Path $taskRoot 'Saved\CodexDDC'),'Process')
 $started=(Get-Date).ToUniversalTime().ToString('o')
 $scriptHash=(Get-FileHash -LiteralPath $taskScript -Algorithm SHA256).Hash.ToLowerInvariant()
 $pluginFlags=@()
 if ($EnableCopyTools) { $pluginFlags=@('-EnablePlugins=CodexHotelAssetTools') }
 & 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' (Join-Path $taskRoot 'HorrorGame.uproject') '-run=pythonscript' ('-script='+$taskScript) '-unattended' '-nop4' '-NullRHI' '-nosplash' '-NoSound' '-NoAutoSave' '-NOINI' '-nocef' '-DDC=InstalledNoZenLocalFallback' '-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path=D:/UE/Project/HorrorGame/Saved/CodexDDC,EnvPathOverride=UE-LocalDataCachePath)' '-stdout' '-FullStdOutLogOutput' '-UTF8Output' @pluginFlags ('-abslog='+(Join-Path $taskWork ($LogName+'.log'))) > (Join-Path $taskWork ($LogName+'.stdout.log')) 2>&1
 $taskExit=$LASTEXITCODE
 [ordered]@{script=$taskScript;script_sha256=$scriptHash;started_utc=$started;log_name=$LogName;exit_code=$taskExit;normal_zero_exit=($taskExit -eq 0);completed_utc=(Get-Date).ToUniversalTime().ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskWork ($LogName+'.Completion.json')) -Encoding utf8
 Write-Output ('HOTEL_DOOR_CLOSURE_HELPER_EXIT='+$taskExit)
 if ($taskExit -ne 0) {throw 'Hotel door closure helper failed'}
} finally {[Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$oldCache,'Process')}


