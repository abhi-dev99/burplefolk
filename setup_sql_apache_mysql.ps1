param(
    [switch]$InstallSSMS = $false,
    [switch]$InstallMySQL80 = $false,
    [string]$SqlServerPackageId = "Microsoft.SQLServer.2025.Developer",
    [switch]$ForceSqlInstall = $false
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) {
    Write-Host "[STEP] $msg" -ForegroundColor Cyan
}

function Ensure-Admin {
    $current = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($current)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Please run this script as Administrator."
    }
}

function Ensure-ServiceInstalled {
    param(
        [string]$ServiceName,
        [scriptblock]$InstallAction
    )

    $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($null -eq $svc) {
        Write-Step "Installing service $ServiceName"
        & $InstallAction
    } else {
        Write-Step "Service $ServiceName already exists"
    }
}

function Start-And-Auto {
    param([string]$ServiceName)

    $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($null -eq $svc) {
        Write-Warning "Service $ServiceName not found after install attempt"
        return
    }

    Set-Service -Name $ServiceName -StartupType Automatic
    if ($svc.Status -ne 'Running') {
        Start-Service -Name $ServiceName
    }
}

function Install-WingetPackage {
    param([string]$Id)

    $winget = "C:/Users/abhi/AppData/Local/Microsoft/WindowsApps/winget.exe"
    if (-not (Test-Path $winget)) {
        throw "winget not found at $winget"
    }

    Write-Step "Installing package $Id"
    & $winget install --id $Id -e --source winget --accept-source-agreements --accept-package-agreements --silent
}

function Get-SqlServerServices {
    $sqlServices = Get-Service -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq "MSSQLSERVER" -or $_.Name -like "MSSQL$*" }
    return @($sqlServices)
}

function Test-SqlSectorCompatibility {
    $disks = Get-PhysicalDisk -ErrorAction SilentlyContinue
    if ($null -eq $disks) {
        return @{ Compatible = $true; Message = "Unable to read physical disk metadata; continuing." }
    }

    $unsupported = @($disks | Where-Object { $_.PhysicalSectorSize -gt 4096 })
    if ($unsupported.Count -eq 0) {
        return @{ Compatible = $true; Message = "Disk sector size check passed (<= 4KB)." }
    }

    $details = ($unsupported | ForEach-Object {
        "$($_.FriendlyName): physical sector $($_.PhysicalSectorSize) bytes"
    }) -join "; "

    return @{
        Compatible = $false
        Message = "SQL Server requires physical sector size <= 4KB. Detected unsupported disk(s): $details"
    }
}

Ensure-Admin

$xamppRoot = "D:/xampp"
$mysqlExe = "$xamppRoot/mysql/bin/mysqld.exe"
$mysqlIni = "$xamppRoot/mysql/bin/my.ini"
$apacheExe = "$xamppRoot/apache/bin/httpd.exe"

if (-not (Test-Path $mysqlExe)) { throw "XAMPP MySQL binary not found at $mysqlExe" }
if (-not (Test-Path $mysqlIni)) { throw "XAMPP MySQL config not found at $mysqlIni" }
if (-not (Test-Path $apacheExe)) { throw "XAMPP Apache binary not found at $apacheExe" }

Ensure-ServiceInstalled -ServiceName "MySQLXAMPP" -InstallAction { & $mysqlExe --install MySQLXAMPP --defaults-file="$mysqlIni" }
Ensure-ServiceInstalled -ServiceName "ApacheXAMPP" -InstallAction { & $apacheExe -k install -n ApacheXAMPP -f "$xamppRoot/apache/conf/httpd.conf" }

Start-And-Auto -ServiceName "MySQLXAMPP"
Start-And-Auto -ServiceName "ApacheXAMPP"

# SQL Server (defaults to 2025 Developer)
$sqlServices = Get-SqlServerServices
if ($sqlServices.Count -eq 0) {
    $sectorCheck = Test-SqlSectorCompatibility
    if (-not $sectorCheck.Compatible -and -not $ForceSqlInstall) {
        Write-Warning $sectorCheck.Message
        Write-Warning "Skipping SQL Server install. Use -ForceSqlInstall only if you are installing to a supported <=4KB sector disk/VHD."
    } else {
        Write-Step $sectorCheck.Message
        Install-WingetPackage -Id $SqlServerPackageId
        $sqlServices = Get-SqlServerServices
    }
} else {
    Write-Step "SQL Server service already present"
}

if ($sqlServices.Count -eq 0) {
    Write-Warning "SQL Server service not found after installer run. Complete installer wizard if prompted, then rerun verification."
} else {
    foreach ($svc in $sqlServices) {
        Start-And-Auto -ServiceName $svc.Name
    }
}

$sqlcmdAvailable = Get-Command sqlcmd -ErrorAction SilentlyContinue
if ($null -eq $sqlcmdAvailable) {
    Install-WingetPackage -Id "Microsoft.Sqlcmd"
} else {
    Write-Step "sqlcmd already available"
}

if ($InstallSSMS) {
    Install-WingetPackage -Id "Microsoft.SQLServerManagementStudio"
}

if ($InstallMySQL80) {
    $mysql80 = Get-Service -Name "MySQL80" -ErrorAction SilentlyContinue
    if ($null -eq $mysql80) {
        Install-WingetPackage -Id "Oracle.MySQL"
        $mysql80 = Get-Service -Name "MySQL80" -ErrorAction SilentlyContinue
    } else {
        Write-Step "MySQL80 service already present"
    }

    if ($null -eq $mysql80) {
        Write-Warning "MySQL80 service was not detected after Oracle.MySQL install. The installer may require interactive configuration."
    } else {
        $port3306InUse = Get-NetTCPConnection -LocalPort 3306 -State Listen -ErrorAction SilentlyContinue
        if ($port3306InUse) {
            Write-Warning "Port 3306 is already in use (likely XAMPP MariaDB). Leaving MySQL80 stopped to avoid conflicts."
            Set-Service -Name "MySQL80" -StartupType Manual
        } else {
            Start-And-Auto -ServiceName "MySQL80"
        }
    }
}

$verify = Get-Service -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match 'MySQLXAMPP|ApacheXAMPP|MySQL80|MSSQLSERVER|MSSQL\$.*' } |
    Select-Object Name, DisplayName, Status, StartType

Write-Host "\n=== Service Verification ===" -ForegroundColor Green
$verify | Format-Table -AutoSize

Write-Host "\nSetup script completed." -ForegroundColor Green
