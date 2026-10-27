param([Parameter(Mandatory=$true)][string]$Script,[Parameter(Mandatory=$true)][string]$LogName)
$ErrorActionPreference='Stop'
$detailRoot='D:\UE\Project\HorrorGame'
$detailWork=Join-Path $detailRoot 'Saved\CodexOutputs\HotelDetails_20261009'
[void](New-Item -ItemType Directory -Path $detailWork -Force)
$detailPreviousCache=[Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
try {
    [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',(Join-Path $detailRoot 'Saved\CodexDDC'),'Process')
    & 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' (Join-Path $detailRoot 'HorrorGame.uproject') '-run=pythonscript' ('-script='+$Script) '-unattended' '-nop4' '-NullRHI' '-nosplash' '-NoSound' '-NoAutoSave' '-nocef' '-DDC=InstalledNoZenLocalFallback' '-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path=D:/UE/Project/HorrorGame/Saved/CodexDDC,EnvPathOverride=UE-LocalDataCachePath)' '-stdout' '-FullStdOutLogOutput' '-UTF8Output' ('-abslog='+ (Join-Path $detailWork ($LogName+'.log'))) > (Join-Path $detailWork ($LogName+'.stdout.log')) 2>&1
    Write-Output ('UE_HELPER_EXIT='+$LASTEXITCODE)
} finally {[Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$detailPreviousCache,'Process')}
