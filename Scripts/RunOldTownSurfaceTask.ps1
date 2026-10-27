param([Parameter(Mandatory=$true)][string]$Script,[Parameter(Mandatory=$true)][string]$LogName)
$ErrorActionPreference='Stop'
$surfaceRoot='D:\UE\Project\HorrorGame'
$surfaceWork=Join-Path $surfaceRoot 'Saved\CodexOutputs\SurfaceSeparation_20261009'
[void](New-Item -ItemType Directory -Path $surfaceWork -Force)
$surfacePreviousCache=[Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
try {
    [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',(Join-Path $surfaceRoot 'Saved\CodexDDC'),'Process')
    & 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' (Join-Path $surfaceRoot 'HorrorGame.uproject') '-run=pythonscript' ('-script='+$Script) '-unattended' '-nop4' '-NullRHI' '-nosplash' '-NoSound' '-NoAutoSave' '-nocef' '-DDC=InstalledNoZenLocalFallback' '-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path=D:/UE/Project/HorrorGame/Saved/CodexDDC,EnvPathOverride=UE-LocalDataCachePath)' '-stdout' '-FullStdOutLogOutput' '-UTF8Output' ('-abslog='+ (Join-Path $surfaceWork ($LogName+'.log'))) > (Join-Path $surfaceWork ($LogName+'.stdout.log')) 2>&1
    Write-Output ('UE_HELPER_EXIT='+$LASTEXITCODE)
} finally {[Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$surfacePreviousCache,'Process')}
