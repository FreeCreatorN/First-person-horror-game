param(
    [Parameter(Mandatory=$true)][string]$Script,
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9_-]+$')][string]$LogName
)
$ErrorActionPreference='Stop'
$refinementRoot='D:\UE\Project\HorrorGame'
$refinementWork=Join-Path $refinementRoot 'Saved\CodexOutputs\OldTownSoftGoodsRefinement_20261013'
$refinementScript=(Resolve-Path -LiteralPath $Script).Path
if (-not $refinementScript.StartsWith((Join-Path $refinementRoot 'Scripts\'),[StringComparison]::OrdinalIgnoreCase)) { throw 'Script escaped workspace.' }
# The user explicitly works in Main while this independent helper owns OldTown.
# No running GUI editor is closed or managed here. Commandlets stay serialized.
$refinementActive=@(Get-Process -Name UnrealEditor-Cmd -ErrorAction SilentlyContinue | Where-Object { -not $_.HasExited })
if ($refinementActive.Count -ne 0) { throw 'Another commandlet is running; no helper launched.' }
$refinementCache=[Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
try {
    [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',(Join-Path $refinementRoot 'Saved\CodexDDC'),'Process')
    & 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' (Join-Path $refinementRoot 'HorrorGame.uproject') `
      '-run=pythonscript' ('-script='+$refinementScript) '-unattended' '-nop4' '-NullRHI' '-nosplash' `
      '-NoSound' '-NoAutoSave' '-NOINI' '-nocef' '-DDC=InstalledNoZenLocalFallback' `
      '-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path=D:/UE/Project/HorrorGame/Saved/CodexDDC,EnvPathOverride=UE-LocalDataCachePath)' `
      '-stdout' '-FullStdOutLogOutput' '-UTF8Output' ('-abslog='+ (Join-Path $refinementWork ($LogName+'.log'))) `
      > (Join-Path $refinementWork ($LogName+'.stdout.log')) 2>&1
    $refinementExit=$LASTEXITCODE
    Write-Output ('UE_HELPER_EXIT='+$refinementExit)
    if ($refinementExit -ne 0) { throw ('Unreal helper failed with exit '+$refinementExit) }
} finally { [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$refinementCache,'Process') }
