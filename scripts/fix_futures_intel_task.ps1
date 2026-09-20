# Requires an elevated PowerShell session.
$ErrorActionPreference = "Stop"

$Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$Principal = [Security.Principal.WindowsPrincipal]::new($Identity)
$IsAdmin = $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $IsAdmin) {
    throw "Run this script from an Administrator PowerShell session."
}

$TaskName = "FuturesIntelDaily"
$ScriptPath = "E:\资讯爬虫\scripts\run_daily.ps1"
if (-not (Test-Path -LiteralPath $ScriptPath)) {
    throw "FuturesIntelTool daily script not found: $ScriptPath"
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$ScriptPath`""

Set-ScheduledTask -TaskName $TaskName -Action $Action | Out-Null
Get-ScheduledTask -TaskName $TaskName |
    Select-Object TaskName, State,
        @{Name="Execute"; Expression={$_.Actions.Execute}},
        @{Name="Arguments"; Expression={$_.Actions.Arguments}},
        @{Name="Start"; Expression={$_.Triggers.StartBoundary}} |
    Format-List
