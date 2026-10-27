param(
 [Parameter(Mandatory=$true)][string]$Script,
 [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9_-]+$')][string]$LogName
)
$ErrorActionPreference='Stop'
$doorRoot='D:\UE\Project\HorrorGame'
$doorWork=Join-Path $doorRoot 'Saved\CodexOutputs\OldTownDoorReuse_20261017'
$doorScript=(Resolve-Path -LiteralPath $Script).Path
if (-not $doorScript.StartsWith((Join-Path $doorRoot 'Scripts\'),[StringComparison]::OrdinalIgnoreCase)) {throw 'Script escaped workspace'}
if (@(Get-Process -Name UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count) {throw 'Another helper is running'}
New-Item -ItemType Directory -Path $doorWork -Force | Out-Null
$doorOldCache=[Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
try {
 [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',(Join-Path $doorRoot 'Saved\CodexDDC'),'Process')
 & 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' (Join-Path $doorRoot 'HorrorGame.uproject') '-run=pythonscript' ('-script='+$doorScript) '-unattended' '-nop4' '-NullRHI' '-nosplash' '-NoSound' '-NoAutoSave' '-NOINI' '-nocef' '-DDC=InstalledNoZenLocalFallback' '-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path=D:/UE/Project/HorrorGame/Saved/CodexDDC,EnvPathOverride=UE-LocalDataCachePath)' '-stdout' '-FullStdOutLogOutput' '-UTF8Output' ('-abslog='+(Join-Path $doorWork ($LogName+'.log'))) > (Join-Path $doorWork ($LogName+'.stdout.log')) 2>&1
 $doorExit=$LASTEXITCODE
 [ordered]@{script=$doorScript;log_name=$LogName;exit_code=$doorExit;normal_zero_exit=($doorExit -eq 0);completed_utc=(Get-Date).ToUniversalTime().ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $doorWork ($LogName+'.Completion.json')) -Encoding utf8
 Write-Output ('DOOR_HELPER_EXIT='+$doorExit)
 if ($doorExit -ne 0) {throw 'Door helper failed'}
} finally {[Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$doorOldCache,'Process')}
