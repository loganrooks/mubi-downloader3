# Setup colors for output
$Green = [System.ConsoleColor]::Green 
$Blue = [System.ConsoleColor]::Blue
$Yellow = [System.ConsoleColor]::Yellow

# Check Python installation
$pythonVersion = python --version 2>&1
if (-not $pythonVersion) {
    Write-Host "Python is not installed or not in PATH. Please install Python 3.7 or higher." -ForegroundColor Red
    exit 1
}

# Extract version number and compare
$versionMatch = $pythonVersion -match '(\d+\.\d+\.\d+)'
if ($versionMatch) {
    $version = [version]$Matches[1]
    $minVersion = [version]"3.7.0"
    if ($version -lt $minVersion) {
        Write-Host "Python version $version is not supported. Please install Python 3.7 or higher." -ForegroundColor Red
        exit 1
    }
}

# Environment checks
Write-Host "Performing environment checks..." -ForegroundColor $Blue

# Check if running with admin privileges (not recommended)
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($isAdmin) {
    Write-Host "Warning: Running with administrator privileges is not recommended." -ForegroundColor $Yellow
}

# Check virtual environment
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor $Blue
    python -m venv .venv
}

# Activate virtual environment
. .\.venv\Scripts\Activate.ps1

# Install requirements if needed
if (-not (Test-Path ".venv\requirements_installed")) {
    Write-Host "Installing requirements..." -ForegroundColor $Blue
    pip install -r requirements.txt
    New-Item -Path ".venv\requirements_installed" -ItemType File
}

# Check for required browser cookies and browser profiles
$browserPaths = @{
    "Chrome" = @(
        "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Cookies",
        "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Network\Cookies"
    )
    "Firefox" = @(
        "$env:APPDATA\Mozilla\Firefox\Profiles"
    )
    "Edge" = @(
        "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Cookies",
        "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Network\Cookies"
    )
}

$browserFound = $false
foreach ($browser in $browserPaths.Keys) {
    $paths = $browserPaths[$browser]
    $found = $false
    
    foreach ($path in $paths) {
        if (Test-Path $path) {
            if (-not $found) {
                Write-Host "Found $browser installation" -ForegroundColor $Green
                $found = $true
                $browserFound = $true
            }
            Write-Host "  - Cookie file: $path" -ForegroundColor $Blue
            
            # Check if we have read access
            try {
                $acl = Get-Acl $path
                $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
                $principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
                $hasAccess = $false
                
                foreach ($rule in $acl.Access) {
                    if ($principal.IsInRole($rule.IdentityReference)) {
                        if ($rule.FileSystemRights -band [System.Security.AccessControl.FileSystemRights]::Read) {
                            $hasAccess = $true
                            break
                        }
                    }
                }
                
                if (-not $hasAccess) {
                    Write-Host "    Warning: Limited read access to cookie file" -ForegroundColor $Yellow
                }
            }
            catch {
                Write-Host "    Warning: Could not check cookie file permissions" -ForegroundColor $Yellow
            }
        }
    }
    
    if ($found -and $browser -eq "Firefox") {
        # For Firefox, check profile folders for cookies.sqlite
        Get-ChildItem "$env:APPDATA\Mozilla\Firefox\Profiles" -Directory | ForEach-Object {
            $cookieFile = Join-Path $_.FullName "cookies.sqlite"
            if (Test-Path $cookieFile) {
                Write-Host "  - Found Firefox profile: $($_.Name)" -ForegroundColor $Blue
            }
        }
    }
}

if (-not $browserFound) {
    Write-Host "Warning: No supported browsers detected. You may need to enter authentication manually." -ForegroundColor $Yellow
}

# Check GUI capability
if (-not [System.Environment]::GetEnvironmentVariable("DISPLAY")) {
    Write-Host "No DISPLAY environment variable set. GUI authentication may not be available." -ForegroundColor $Yellow
}

# Add the src directory to PYTHONPATH
$env:PYTHONPATH = "$env:PYTHONPATH;$(Get-Location)"

# Run the mubi downloader
Write-Host "Starting Mubi Downloader..." -ForegroundColor $Green
python -m src.mubi_downloader $args

# Deactivate virtual environment
deactivate