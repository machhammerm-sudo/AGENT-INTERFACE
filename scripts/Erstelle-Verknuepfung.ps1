# Erstellt eine Desktop-Verknuepfung "Nauteron" mit eigenem Icon,
# die beim Doppelklick Nauteron-Starten.bat ausfuehrt.

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DesktopPath = [Environment]::GetFolderPath("Desktop")

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut((Join-Path $DesktopPath "Nauteron.lnk"))
$Shortcut.TargetPath = Join-Path $ProjectRoot "Nauteron-Starten.bat"
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.IconLocation = Join-Path $ProjectRoot "assets\nauteron-icon.ico"
$Shortcut.Description = "Nauteron Cockpit starten"
$Shortcut.Save()

Write-Host ""
Write-Host "Fertig! Auf deinem Desktop liegt jetzt eine Verknuepfung namens Nauteron."
Write-Host "Einfach doppelklicken, um das Cockpit zu starten."
