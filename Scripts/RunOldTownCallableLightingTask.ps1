param(
    [Parameter(Mandatory=$true)][string]$Script,
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9_-]+$')][string]$LogName
)
$ErrorActionPreference='Stop'
$lightingRoot='D:\UE\Project\HorrorGame'
$lightingWork=Join-Path $lightingRoot 'Saved\CodexOutputs\OldTownCallableLighting_20261016'
$lightingScript=(Resolve-Path -LiteralPath $Script).Path
if (-not $lightingScript.StartsWith((Join-Path $lightingRoot 'Scripts\'),[StringComparison]::OrdinalIgnoreCase)) { throw 'Script escaped workspace.' }
if (@(Get-Process -Name UnrealEditor-Cmd -ErrorAction SilentlyContinue).Count -ne 0) { throw 'Another helper is running.' }
$lightingCache=[Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
try {
    [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',(Join-Path $lightingRoot 'Saved\CodexDDC'),'Process')
    & 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' (Join-Path $lightingRoot 'HorrorGame.uproject') `
      '-run=pythonscript' ('-script='+$lightingScript) '-unattended' '-nop4' '-NullRHI' '-nosplash' `
      '-NoSound' '-NoAutoSave' '-NOINI' '-nocef' '-DDC=InstalledNoZenLocalFallback' `
      '-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path=D:/UE/Project/HorrorGame/Saved/CodexDDC,EnvPathOverride=UE-LocalDataCachePath)' `
      '-stdout' '-FullStdOutLogOutput' '-UTF8Output' ('-abslog='+ (Join-Path $lightingWork ($LogName+'.log'))) `
      > (Join-Path $lightingWork ($LogName+'.stdout.log')) 2>&1
    $lightingExit=$LASTEXITCODE
    Write-Output ('UE_HELPER_EXIT='+$lightingExit)
    [ordered]@{script=$lightingScript;log_name=$LogName;exit_code=$lightingExit;normal_zero_exit=($lightingExit -eq 0);completed_utc=(Get-Date).ToUniversalTime().ToString('o')} |
      ConvertTo-Json | Set-Content -LiteralPath (Join-Path $lightingWork ($LogName+'.Completion.json')) -Encoding utf8
    if ($lightingExit -ne 0) { throw ('Unreal helper failed with exit '+$lightingExit) }
} finally { [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$lightingCache,'Process') }
