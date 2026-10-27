param(
    [Parameter(Mandatory=$true)][string]$Script,
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9_-]+$')][string]$LogName
)
$ErrorActionPreference='Stop'
$realismRoot='D:\UE\Project\HorrorGame'
$realismWork=Join-Path $realismRoot 'Saved\CodexOutputs\OldTownRealism_20261012'
$realismScript=(Resolve-Path -LiteralPath $Script).Path
if (-not $realismScript.StartsWith((Join-Path $realismRoot 'Scripts\'),[StringComparison]::OrdinalIgnoreCase)) {
    throw 'The task script must be in this workspace Scripts directory.'
}
$realismActiveEditors=@(Get-Process -Name UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue | Where-Object { -not $_.HasExited })
if ($realismActiveEditors.Count -ne 0) { throw 'An Unreal editor is already running; no second helper was launched.' }
$realismCacheBefore=[Environment]::GetEnvironmentVariable('UE-LocalDataCachePath','Process')
try {
    [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',(Join-Path $realismRoot 'Saved\CodexDDC'),'Process')
    & 'D:\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' (Join-Path $realismRoot 'HorrorGame.uproject') `
        '-run=pythonscript' ('-script='+$realismScript) '-unattended' '-nop4' '-NullRHI' '-nosplash' `
        '-NoSound' '-NoAutoSave' '-nocef' '-DDC=InstalledNoZenLocalFallback' `
        '-ini:Engine:[InstalledDerivedDataBackendGraph]:Local=(Type=FileSystem,UnusedFileAge=34,Path=D:/UE/Project/HorrorGame/Saved/CodexDDC,EnvPathOverride=UE-LocalDataCachePath)' `
        '-stdout' '-FullStdOutLogOutput' '-UTF8Output' ('-abslog='+ (Join-Path $realismWork ($LogName+'.log'))) `
        > (Join-Path $realismWork ($LogName+'.stdout.log')) 2>&1
    $realismExitCode=$LASTEXITCODE
    Write-Output ('UE_HELPER_EXIT='+$realismExitCode)
    if ($realismExitCode -ne 0) { throw ('Unreal helper failed with exit '+$realismExitCode) }
} finally {
    [Environment]::SetEnvironmentVariable('UE-LocalDataCachePath',$realismCacheBefore,'Process')
}
