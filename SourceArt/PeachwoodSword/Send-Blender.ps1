param([string]$ScriptPath)
$request = @{op='status'}
if ($ScriptPath) { $request = @{op='execute';code=[IO.File]::ReadAllText((Resolve-Path -LiteralPath $ScriptPath))} }
$client = [Net.Sockets.TcpClient]::new()
try {
    $client.Connect('127.0.0.1',9876)
    $stream = $client.GetStream()
    $stream.ReadTimeout = 300000
    $writer = [IO.StreamWriter]::new($stream,[Text.UTF8Encoding]::new($false))
    $writer.AutoFlush = $true
    $reader = [IO.StreamReader]::new($stream,[Text.Encoding]::UTF8)
    $writer.WriteLine(($request | ConvertTo-Json -Compress))
    $reader.ReadLine()
} finally { $client.Dispose() }
