$ErrorActionPreference = "Continue"

$services = @("SQLSERVERAGENT", "MSSQLSERVER", "SQLBrowser", "SQLWriter")
foreach ($svc in $services) {
    try {
        Stop-Service -Name $svc -Force -ErrorAction SilentlyContinue
    } catch {
    }
    try {
        sc.exe delete $svc | Out-Null
    } catch {
    }
}

$paths = @(
    "C:\SQL2025",
    "C:\Program Files\Microsoft SQL Server",
    "C:\Program Files (x86)\Microsoft SQL Server"
)

foreach ($path in $paths) {
    if (Test-Path $path) {
        try {
            Remove-Item -Path $path -Recurse -Force -ErrorAction Stop
            Write-Host "Removed: $path"
        } catch {
            Write-Warning "Could not remove: $path | $($_.Exception.Message)"
        }
    } else {
        Write-Host "Already absent: $path"
    }
}

Write-Host "Cleanup completed."
