[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$CloudUrl = "https://ai-zoo-zombie.zeabur.app"
$AgentArchiveUrl = "$CloudUrl/windows-client/print-agent.zip"
$InstallRoot = Join-Path $env:LOCALAPPDATA "AI-ZOO"
$RuntimeRoot = Join-Path $InstallRoot "runtime"
$AgentRoot = Join-Path $InstallRoot "print-agent"
$TerminalFile = Join-Path $InstallRoot "terminal-id.txt"
$RunnerFile = Join-Path $InstallRoot "run-print-agent.cmd"
$LogFile = Join-Path $InstallRoot "print-agent.log"
$StartupFolder = [Environment]::GetFolderPath("Startup")
$DesktopFolder = [Environment]::GetFolderPath("Desktop")
$StartupShortcut = Join-Path $StartupFolder "AI-ZOO-Print-Agent.lnk"
$KioskShortcut = Join-Path $DesktopFolder "AI ZOO Photo Kiosk.url"
$WindowsPowerShellExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$WindowsCmdExe = Join-Path $env:SystemRoot "System32\cmd.exe"
$WindowsChcpExe = Join-Path $env:SystemRoot "System32\chcp.com"
$WindowsSystemPath = @(
    (Join-Path $env:SystemRoot "System32"),
    (Join-Path $env:SystemRoot "System32\Wbem"),
    (Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0")
) -join ";"

function Write-Step([string]$Message) {
    Write-Host "`n[AI ZOO] $Message" -ForegroundColor Cyan
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Restart-AsAdministrator {
    Write-Step "Windows will request administrator permission to detect the USB printer."
    $arguments = @(
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", ('"{0}"' -f $PSCommandPath)
    )
    $process = Start-Process -FilePath $WindowsPowerShellExe -Verb RunAs -ArgumentList $arguments -Wait -PassThru
    exit $process.ExitCode
}

function Get-InstalledPrinters {
    try {
        return @(Get-Printer -ErrorAction Stop)
    }
    catch {
        return @(
            Get-CimInstance Win32_Printer -ErrorAction SilentlyContinue |
                ForEach-Object {
                    [PSCustomObject]@{
                        Name = $_.Name
                        DriverName = $_.DriverName
                        PortName = $_.PortName
                    }
                }
        )
    }
}

function Find-SelphyPrinter {
    $printers = @(Get-InstalledPrinters)
    return $printers | Where-Object {
        ("$($_.Name) $($_.DriverName)" -match "(?i)Canon.*(?:SELPHY.*)?CP\s*1500|SELPHY.*CP\s*1500")
    } | Select-Object -First 1
}

function Initialize-Printer {
    Write-Step "Detecting the connected Canon SELPHY printer..."
    $windows = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
    if ($windows -and [int]$windows.BuildNumber -lt 22000) {
        Write-Warning "Canon supports CP1500 USB printing on Windows 11. This computer reports build $($windows.BuildNumber); Windows 10 may not create a usable CP1500 queue."
    }
    Set-Service -Name Spooler -StartupType Automatic -ErrorAction SilentlyContinue
    Start-Service -Name Spooler -ErrorAction SilentlyContinue
    & "$env:SystemRoot\System32\pnputil.exe" /scan-devices | Out-Null

    $printer = $null
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        $printer = Find-SelphyPrinter
        if ($printer) { break }
        if ($attempt -eq 5) {
            Write-Host "Waiting for Windows to install the USB printer driver..." -ForegroundColor Yellow
            $updateClient = Join-Path $env:SystemRoot "System32\UsoClient.exe"
            if (Test-Path $updateClient) { & $updateClient StartScan 2>$null }
        }
        Start-Sleep -Seconds 2
    }
    if (-not $printer) {
        Write-Warning "No physical printer queue was found. The agent will still be installed."
        Write-Host "Keep the printer powered on, then use Windows Settings > Bluetooth & devices > Printers & scanners > Add device." -ForegroundColor Yellow
        Start-Process "ms-settings:printers" -ErrorAction SilentlyContinue
        return $null
    }

    try {
        New-ItemProperty -Path "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Windows" -Name "LegacyDefaultPrinterMode" -PropertyType DWord -Value 1 -Force | Out-Null
        $network = New-Object -ComObject WScript.Network
        $network.SetDefaultPrinter($printer.Name)
    }
    catch {
        Write-Warning "Printer was detected but Windows did not allow changing the default printer: $($_.Exception.Message)"
    }

    Write-Host "Printer ready: $($printer.Name)" -ForegroundColor Green
    return $printer
}

function Install-PortableNode {
    $existingNode = Get-ChildItem -Path $RuntimeRoot -Filter node.exe -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($existingNode) { return $existingNode.FullName }

    Write-Step "Downloading the portable Node.js runtime (nothing is installed system-wide)..."
    New-Item -ItemType Directory -Path $RuntimeRoot -Force | Out-Null
    $nodeMirror = "https://npmmirror.com/mirrors/node/latest-v20.x"
    $checksums = (Invoke-WebRequest -UseBasicParsing "$nodeMirror/SHASUMS256.txt").Content
    $archiveName = [regex]::Match($checksums, "node-v[0-9.]+-win-x64\.zip").Value
    if (-not $archiveName) { throw "Could not resolve the current Node.js 20 Windows archive." }
    $checksumLine = @($checksums -split "`r?`n" | Where-Object { $_ -match ("\s" + [regex]::Escape($archiveName) + "$") })[0]
    if (-not $checksumLine) { throw "Could not resolve the Node.js archive checksum." }
    $expectedHash = @($checksumLine -split "\s+")[0].ToLowerInvariant()

    $archivePath = Join-Path $env:TEMP $archiveName
    $extractRoot = Join-Path $env:TEMP ("AI-ZOO-node-" + [guid]::NewGuid().ToString("N"))
    Invoke-WebRequest -UseBasicParsing "$nodeMirror/$archiveName" -OutFile $archivePath
    $actualHash = (Get-FileHash -Path $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $expectedHash) { throw "The downloaded Node.js archive failed SHA-256 verification." }
    Expand-Archive -Path $archivePath -DestinationPath $extractRoot -Force
    $nodeDirectory = Get-ChildItem -Path $extractRoot -Directory | Select-Object -First 1
    if (-not $nodeDirectory) { throw "The portable Node.js archive is invalid." }

    $targetDirectory = Join-Path $RuntimeRoot $nodeDirectory.Name
    if (Test-Path $targetDirectory) { Remove-Item -Path $targetDirectory -Recurse -Force }
    Move-Item -Path $nodeDirectory.FullName -Destination $targetDirectory -Force
    Remove-Item -Path $archivePath -Force -ErrorAction SilentlyContinue
    Remove-Item -Path $extractRoot -Recurse -Force -ErrorAction SilentlyContinue
    return (Join-Path $targetDirectory "node.exe")
}

function Install-PrintAgent([string]$NodeExe) {
    $electronCommand = Join-Path $AgentRoot "node_modules\.bin\electron.cmd"
    if (Test-Path $electronCommand) { return }

    Write-Step "Downloading and installing the AI ZOO Windows print service..."
    $sourceArchive = Join-Path $env:TEMP "AI-ZOO-print-agent.zip"
    Invoke-WebRequest -UseBasicParsing $AgentArchiveUrl -OutFile $sourceArchive

    New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
    if (Test-Path $AgentRoot) { Remove-Item -Path $AgentRoot -Recurse -Force }
    New-Item -ItemType Directory -Path $AgentRoot -Force | Out-Null
    Expand-Archive -Path $sourceArchive -DestinationPath $AgentRoot -Force
    if (-not (Test-Path (Join-Path $AgentRoot "package.json"))) {
        throw "The downloaded print service archive is invalid."
    }
    Remove-Item -Path $sourceArchive -Force -ErrorAction SilentlyContinue

    $nodeDirectory = Split-Path $NodeExe -Parent
    $npmCommand = Join-Path $nodeDirectory "npm.cmd"
    $oldPath = $env:PATH
    $env:PATH = "$nodeDirectory;$WindowsSystemPath;$env:PATH"
    $env:npm_config_cache = Join-Path $InstallRoot "npm-cache"
    $env:npm_config_registry = "https://registry.npmmirror.com"
    $env:npm_config_sqlite3_binary_host_mirror = "https://npmmirror.com/mirrors/sqlite3"
    $env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
    try {
        Push-Location $AgentRoot
        $packageLock = Join-Path $AgentRoot "package-lock.json"
        if (Test-Path $packageLock) {
            & $npmCommand ci --no-audit --no-fund
            $npmExitCode = $LASTEXITCODE
            if ($npmExitCode -ne 0) {
                Write-Warning "npm ci failed; retrying with npm install."
                & $npmCommand install --no-audit --no-fund --package-lock=false
                $npmExitCode = $LASTEXITCODE
            }
        }
        else {
            Write-Warning "The archive has no package-lock.json; using npm install compatibility mode."
            & $npmCommand install --no-audit --no-fund --package-lock=false
            $npmExitCode = $LASTEXITCODE
        }
        if ($npmExitCode -ne 0) { throw "npm dependency installation exited with code $npmExitCode." }
    }
    finally {
        Pop-Location
        $env:PATH = $oldPath
    }

    if (-not (Test-Path $electronCommand)) { throw "Electron print service installation is incomplete." }
}

function Get-TerminalId {
    if (Test-Path $TerminalFile) {
        $saved = (Get-Content $TerminalFile -Raw).Trim()
        if ($saved -match "^[A-Za-z0-9_-]{32,128}$") { return $saved }
    }
    $created = [guid]::NewGuid().ToString("N")
    Set-Content -Path $TerminalFile -Value $created -NoNewline -Encoding Ascii
    return $created
}

function Write-LaunchFiles([string]$NodeExe, [string]$TerminalId) {
    $nodeDirectory = Split-Path $NodeExe -Parent
    $agentBin = Join-Path $AgentRoot "node_modules\.bin"
    $runner = @"
@echo off
"$WindowsChcpExe" 65001 >nul
cd /d "$AgentRoot"
set "AI_ZOO_PRINT_RELAY_URL=$CloudUrl"
set "AI_ZOO_TERMINAL_ID=$TerminalId"
set "AI_ZOO_FIELD_MODE=1"
set "PATH=$nodeDirectory;$agentBin;$WindowsSystemPath;%PATH%"
"$NodeExe" build\write-build-info.js >> "$LogFile" 2>&1
"$NodeExe" start.js >> "$LogFile" 2>&1
"@
    $utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($RunnerFile, $runner, $utf8WithoutBom)

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($StartupShortcut)
    $shortcut.TargetPath = $WindowsCmdExe
    $shortcut.Arguments = "/c `"`"$RunnerFile`"`""
    $shortcut.WorkingDirectory = $AgentRoot
    $shortcut.WindowStyle = 7
    $shortcut.Description = "AI ZOO cloud print service"
    $shortcut.Save()

    $kioskUrl = "$CloudUrl/kiosk/?terminal=$TerminalId"
    Set-Content -Path $KioskShortcut -Encoding Ascii -Value @(
        "[InternetShortcut]",
        "URL=$kioskUrl",
        "IconFile=$env:SystemRoot\System32\shell32.dll",
        "IconIndex=220"
    )
    return $kioskUrl
}

try {
    if (-not (Test-IsAdministrator)) { Restart-AsAdministrator }

    Write-Host "===============================================" -ForegroundColor DarkCyan
    Write-Host " AI ZOO - Windows one-click field setup" -ForegroundColor White
    Write-Host "===============================================" -ForegroundColor DarkCyan
    New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null

    $printer = Initialize-Printer
    $nodeExe = Install-PortableNode
    Install-PrintAgent -NodeExe $nodeExe
    $terminalId = Get-TerminalId
    $kioskUrl = Write-LaunchFiles -NodeExe $nodeExe -TerminalId $terminalId

    Write-Step "Starting the background print service and opening the kiosk..."
    Start-Process -FilePath $WindowsCmdExe -ArgumentList "/c", ('"{0}"' -f $RunnerFile) -WindowStyle Hidden
    Start-Sleep -Seconds 5
    Start-Process $kioskUrl

    Write-Host "`nSetup complete." -ForegroundColor Green
    Write-Host "Terminal ID: $terminalId"
    if ($printer) { Write-Host "Printer: $($printer.Name)" }
    Write-Host "Desktop shortcut: $KioskShortcut"
    Write-Host "The print service will start automatically whenever this Windows user signs in."
    Write-Host "On the first photo, allow the browser to use the camera."
    Write-Host "`nYou can close this window." -ForegroundColor Green
    Read-Host "Press Enter to finish" | Out-Null
    exit 0
}
catch {
    Write-Host "`nAI ZOO setup failed:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "`nLog location after the agent starts: $LogFile"
    Read-Host "Press Enter to close" | Out-Null
    exit 1
}
