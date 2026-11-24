$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$result = 0
$logging = $false
function Find-Python311 {
    $candidates = @()
    if (Get-Command py.exe -ErrorAction SilentlyContinue) { $candidates += ,@('py.exe', '-3.11') }
    $candidates += ,@("$env:LOCALAPPDATA\Programs\Python\Python311\python.exe")
    $candidates += ,@("$env:ProgramFiles\Python311\python.exe")
    if (Get-Command python.exe -ErrorAction SilentlyContinue) { $candidates += ,@('python.exe') }
    foreach ($candidate in $candidates) {
        $exe = $candidate[0]
        $prefix = @($candidate | Select-Object -Skip 1)
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        try {
            & $exe @prefix -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 11) else 1)' 2>$null
            if ($LASTEXITCODE -eq 0) { return $candidate }
        } catch { continue }
    }
}
try {
    Start-Transcript -Path (Join-Path $projectRoot 'setup.log') -Force | Out-Null
    $logging = $true
    Write-Host '[1/3] Checking Python 3.11...'
    $python = @(Find-Python311)
    if ($python.Count -eq 0) {
        if (Get-Command winget.exe -ErrorAction SilentlyContinue) {
            Write-Host 'Installing Python 3.11 using Windows Package Manager...'
            & winget.exe install --id Python.Python.3.11 --exact --source winget --scope user --accept-source-agreements --accept-package-agreements
            if ($LASTEXITCODE -ne 0) {
                Write-Host 'Windows Package Manager failed. Trying the official Python installer...'
            }
            $python = @(Find-Python311)
        }
        if ($python.Count -eq 0) {
            if (-not [Environment]::Is64BitOperatingSystem) {
                throw 'This project requires 64-bit Windows for its speech recognition dependencies.'
            }
            Write-Host 'Downloading Python 3.11.9 (64-bit) from python.org...'
            [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
            $downloadDir = Join-Path ([IO.Path]::GetTempPath()) ([Guid]::NewGuid().ToString())
            New-Item -ItemType Directory -Path $downloadDir | Out-Null
            $installer = Join-Path $downloadDir 'python-3.11.9-amd64.exe'
            try {
                Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile $installer
                $signature = Get-AuthenticodeSignature -FilePath $installer
                if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Python Software Foundation(?:,|$)') {
                    throw 'Python installer signature verification failed. Installation was stopped.'
                }
                Write-Host 'Installing Python for your Windows user. Please wait...'
                $installProcess = Start-Process -FilePath $installer -ArgumentList @('/quiet', 'InstallAllUsers=0', 'Include_launcher=0', 'Include_test=0', 'Include_pip=1', 'PrependPath=0', '/log', ('"' + (Join-Path $projectRoot 'python-install.log') + '"')) -Wait -PassThru
                if ($installProcess.ExitCode -notin @(0, 3010)) {
                    throw "Python installation failed (exit code $($installProcess.ExitCode)). See python-install.log."
                }
            } finally {
                Remove-Item -LiteralPath $downloadDir -Recurse -Force
            }
        }
        $python = @(Find-Python311)
        if ($python.Count -eq 0) { throw 'Python could not be located. Reopen setup.bat, or install Python 3.11 manually.' }
    }
    $exe = $python[0]
    $prefix = @($python | Select-Object -Skip 1)
    Write-Host '[2/3] Rebuilding .venv for this computer (replaces generated dependencies)...'
    & $exe @prefix -m venv --clear (Join-Path $projectRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not rebuild .venv. Close running project Python processes and retry.' }
    $venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
    Write-Host '[3/3] Installing dependencies. This may take several minutes...'
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'Could not update pip. Check your internet connection and the error above.' }
    & $venvPython -m pip install -r (Join-Path $projectRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the error above.' }
    & $venvPython -c 'import faster_whisper, soundfile, noisereduce, scipy'
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Checking Microsoft Visual C++ runtime. Windows may request administrator approval.'
        $runtimeDir = Join-Path ([IO.Path]::GetTempPath()) ([Guid]::NewGuid().ToString())
        New-Item -ItemType Directory -Path $runtimeDir | Out-Null
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
            $runtimeInstaller = Join-Path $runtimeDir 'vc_redist.x64.exe'
            Invoke-WebRequest -UseBasicParsing -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile $runtimeInstaller
            $runtimeSignature = Get-AuthenticodeSignature -FilePath $runtimeInstaller
            if ($runtimeSignature.Status -ne 'Valid' -or $runtimeSignature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation(?:,|$)') {
                throw 'Microsoft runtime installer signature verification failed.'
            }
            $runtimeProcess = Start-Process -FilePath $runtimeInstaller -ArgumentList @('/install', '/quiet', '/norestart') -Wait -PassThru
            if ($runtimeProcess.ExitCode -notin @(0, 1638, 3010)) {
                throw "Microsoft runtime installation failed (exit code $($runtimeProcess.ExitCode))."
            }
        } finally {
            Remove-Item -LiteralPath $runtimeDir -Recurse -Force
        }
        & $venvPython -c 'import faster_whisper, soundfile, noisereduce, scipy'
        if ($LASTEXITCODE -ne 0) { throw 'Dependency verification failed after Microsoft runtime installation. See setup.log.' }
    }
    & $venvPython (Join-Path $projectRoot 'py\runtime.py') --setup
    if ($LASTEXITCODE -ne 0) { throw 'Transcription verification failed. See runtime-check.log.' }
    Write-Host 'Setup complete. Double-click run_transcribe.bat.' -ForegroundColor Green
    Write-Host 'Speech model downloaded and transcription verified. GPU is used when its check passes; otherwise CPU is used.'
} catch {
    Write-Host "Setup failed: $($_.Exception.Message)" -ForegroundColor Red
    $result = 1
} finally {
    if ($logging) { Stop-Transcript | Out-Null }
}
exit $result
