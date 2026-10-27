param([Parameter(Mandatory=$true)][string]$Script,[Parameter(Mandatory=$true)][string]$LogName,[string]$OutputDirectory='Saved\CodexOutputs\BasinConnections_20261011')
$ErrorActionPreference='Stop'
$basinRoot='D:\UE\Project\HorrorGame'
$basinWork=[System.IO.Path]::GetFullPath((Join-Path $basinRoot $OutputDirectory))
if(-not $basinWork.StartsWith(($basinRoot+'\Saved\CodexOutputs\'),[System.StringComparison]::OrdinalIgnoreCase)){throw 'Helper output must remain in project Saved/CodexOutputs'}
[void](New-Item -ItemType Directory -Path $basinWork -Force)
$basinPreviousCache=[Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
try {
    [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',(Join-Path $basinRoot 'Saved\CodexDDC'),'Process')
    & 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' (Join-Path $basinRoot 'HorrorGame.uproject') '-run=pythonscript' ('-script='+$Script) '-unattended' '-nop4' '-NullRHI' '-nosplash' '-NoSound' '-NoAutoSave' '-nocef' '-DDC=InstalledNoZenLocalFallback' '-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path=D:/UE/Project/HorrorGame/Saved/CodexDDC,EnvPathOverride=UE-LocalDataCachePath)' '-stdout' '-FullStdOutLogOutput' '-UTF8Output' ('-abslog='+ (Join-Path $basinWork ($LogName+'.log'))) > (Join-Path $basinWork ($LogName+'.stdout.log')) 2>&1
    $basinExit=$LASTEXITCODE
    Write-Output ('UE_HELPER_EXIT='+$basinExit)
    if($basinExit -ne 0){throw ('Basin helper failed: '+$basinExit)}
} finally {[Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$basinPreviousCache,'Process')}
