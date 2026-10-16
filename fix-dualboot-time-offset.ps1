New-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\TimeZoneInformation' `
    -Name RealTimeIsUniversal -PropertyType DWord -Value 1 -Force | Out-Null

Write-Host "RealTimeIsUniversal = 1 set. Reboot for it to take effect."
