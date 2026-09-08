$ports = @(5173, 8000)
$stopped = @()

foreach ($port in $ports) {
    $listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        if ($listener.OwningProcess -and $stopped -notcontains $listener.OwningProcess) {
            Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
            $stopped += $listener.OwningProcess
        }
    }
}

Write-Host "Northstar stopped. Your SQLite data and snapshots were preserved." -ForegroundColor Green
