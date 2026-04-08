param(
    [string]$DesktopPath = [Environment]::GetFolderPath('Desktop')
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$shell = New-Object -ComObject WScript.Shell

$shortcuts = @(
    @{
        Name = 'Bot Society Markets Dashboard.lnk'
        Target = Join-Path $root 'launch-dashboard.bat'
        Arguments = ''
        Description = 'Start Bot Society Markets and open the dashboard.'
        Icon = 'C:\Program Files\Docker\Docker\Docker Desktop.exe,0'
    },
    @{
        Name = 'Stop Bot Society Markets.lnk'
        Target = Join-Path $root 'stop-docker.bat'
        Arguments = ''
        Description = 'Stop the Bot Society Markets Docker stack.'
        Icon = 'C:\Windows\System32\SHELL32.dll,27'
    }
)

foreach ($item in $shortcuts) {
    $shortcutPath = Join-Path $DesktopPath $item.Name
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $item.Target
    $shortcut.Arguments = $item.Arguments
    $shortcut.WorkingDirectory = $root
    $shortcut.Description = $item.Description
    $shortcut.IconLocation = $item.Icon
    $shortcut.Save()
    Write-Host "Created $shortcutPath"
}
