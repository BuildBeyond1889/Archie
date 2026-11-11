@echo off
REM One-time: lets Archie Lite on your laptop reach Archie on this PC.
REM Opens only Archie Lite's two ports, and only to private home-network addresses (192.168.x, 10.x, 172.16-31.x) and Tailscale (100.64-127.x).
REM Windows will ask for permission (admin) once.

net session >nul 2>&1
if %errorlevel% neq 0 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

netsh advfirewall firewall delete rule name="Archie Lite sync (TCP)" >nul 2>&1
netsh advfirewall firewall delete rule name="Archie Lite find PC (UDP)" >nul 2>&1
netsh advfirewall firewall add rule name="Archie Lite sync (TCP)" dir=in action=allow protocol=TCP localport=47321 remoteip=localsubnet,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,100.64.0.0/10 profile=any
netsh advfirewall firewall add rule name="Archie Lite find PC (UDP)" dir=in action=allow protocol=UDP localport=47322 remoteip=localsubnet,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,100.64.0.0/10 profile=any

echo.
powershell -NoProfile -Command "$b = Get-NetFirewallRule -Direction Inbound -Action Block -Enabled True -ErrorAction SilentlyContinue | Where-Object { ($_ | Get-NetFirewallApplicationFilter).Program -match 'python' }; if ($b) { Write-Host 'WARNING: Windows has a rule BLOCKING Python from the network (made when a firewall pop-up was declined).'; Write-Host 'It overrides the rules above. Remove it in Windows Security, Firewall, Advanced settings, Inbound Rules:'; $b | ForEach-Object { Write-Host ('  - ' + $_.DisplayName + ' (' + $_.Profile + ')') } }"
echo Done. Archie Lite on your laptop can now find this PC on your home network.
echo (Only the paired laptop can actually sync: everything is encrypted with the pairing key.)
echo To undo: Windows Security, Firewall, Advanced settings, Inbound Rules, delete the two "Archie Lite" rules.
pause
