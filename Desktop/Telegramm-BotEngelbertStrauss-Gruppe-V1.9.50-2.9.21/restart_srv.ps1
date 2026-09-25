Get-CimInstance Win32_Process -Filter "CommandLine LIKE '%web_dashboard/app.py%'" | Stop-Process -Force
Write-Host "Restarting server via monitor..."
