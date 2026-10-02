$ErrorActionPreference = "Stop"

# Create virtual environment if it doesn't exist
$venvPython = ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment..."
    $pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pythonLauncher) {
        & $pythonLauncher.Source -3 -m venv .venv
    } else {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonCommand) {
            throw "Python 3.12 or newer is required. Install Python and ensure it is on PATH."
        }
        & $pythonCommand.Source -m venv .venv
    }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) {
        throw "Could not create the virtual environment. Install Python 3.12 or newer and try again."
    }
}

# Install or update dependencies
Write-Host "Checking and installing dependencies..."
& $venvPython -m pip install --upgrade pip -q
if ($LASTEXITCODE -ne 0) {
    throw "Could not upgrade pip in the ForceX virtual environment."
}
& $venvPython -m pip install -r requirements.txt -q
if ($LASTEXITCODE -ne 0) {
    throw "Could not install ForceX dependencies."
}

# Create and configure .env if it doesn't exist
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env file..."
    Copy-Item .env.example .env
    
    # Generate keys
    $secretKey = & $venvPython -c "import secrets; print(secrets.token_hex(32))"
    $clientKey = & $venvPython -c "import secrets; print(secrets.token_hex(32))"
    
    # Replace the placeholder keys in the .env file
    (Get-Content .env) -replace '^FORCEX_SECRET_KEY=.*', ("FORCEX_SECRET_KEY=" + $secretKey) | 
    ForEach-Object { $_ -replace '^FORCEX_CLIENT_KEY=.*', ("FORCEX_CLIENT_KEY=" + $clientKey) } | 
    Set-Content .env
    
    Write-Host "Generated new FORCEX_SECRET_KEY and FORCEX_CLIENT_KEY."
}

# Start the application
Write-Host "Starting ForceX server..."
& $venvPython run.py
