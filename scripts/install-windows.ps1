param([switch]$Check)

$ErrorActionPreference = 'Stop'
$ForgeVersion = '1.2.9'

function Has-Tool($Name) { return [bool](Get-Command $Name -ErrorAction SilentlyContinue) }
function Missing($Name) { Write-Output "Missing: $Name" }
function Install-Package($Label, $Command, $Id) {
    if (Has-Tool $Command) {
        if (-not $Check) { Write-Output "$Label is ready." }
        return
    }
    if ($Check) { Missing $Label; return }
    Write-Output "Installing $Label..."
    & winget install --id $Id --exact --source winget --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw "$Label did not install. Check the message above, then run this script again." }
}
function Browsers-Present {
    $root = Join-Path $env:LOCALAPPDATA 'ms-playwright'
    foreach ($kind in @('chromium', 'firefox', 'webkit')) {
        if (-not (Get-ChildItem -Path $root -Directory -Filter "$kind-*" -ErrorAction SilentlyContinue)) { return $false }
    }
    return $true
}

if (-not (Has-Tool winget)) {
    if ($Check) { Missing 'Windows Package Manager (winget)' }
    else { throw 'Windows Package Manager is missing. Install App Installer from Microsoft Store, then run this script again.' }
}

Install-Package 'Git' git 'Git.Git'
Install-Package 'GitHub CLI' gh 'GitHub.cli'
Install-Package 'Node' node 'OpenJS.NodeJS.LTS'
Install-Package 'uv' uv 'astral-sh.uv'

$wslStatus = ''
if (Has-Tool wsl) {
    # wsl.exe exists but fails with an error when WSL is not installed; Windows PowerShell 5.1
    # would stop the script on that redirected error, so any failure here means WSL2 is missing.
    $ErrorActionPreference = 'Continue'
    try {
        $wslStatus = & wsl --status 2>$null
        if ($LASTEXITCODE -ne 0) { $wslStatus = '' }
    } catch { $wslStatus = '' }
    finally { $ErrorActionPreference = 'Stop' }
}
$wslReady = $wslStatus -match 'Default Version: 2'
if (-not $wslReady) {
    if ($Check) { Missing 'WSL2 for Docker' }
    else {
        # FORGE_INSTALL_ADMIN (1 or 0) lets the tests choose either path on any runner.
        $isAdmin = if ($env:FORGE_INSTALL_ADMIN) { $env:FORGE_INSTALL_ADMIN -eq '1' } else {
            ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
                [Security.Principal.WindowsBuiltInRole]::Administrator)
        }
        if (-not $isAdmin) {
            Write-Output 'Docker needs WSL2. Open PowerShell as administrator, run this script again, then restart your laptop once.'
            exit 1
        }
        Write-Output 'Switching on WSL2 for Docker. Restart your laptop once after setup, then run this script again.'
        if ($wslStatus -match 'Default Version: 1') {
            & dism /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
            # 3010 means the feature is on and Windows wants a restart.
            if ($LASTEXITCODE -notin 0, 3010) { throw 'WSL2 could not be switched on. Check the message above, then run this script again as administrator.' }
            if ($LASTEXITCODE -eq 3010) { Write-Output 'Windows asks for a restart: restart your laptop, then run this script again.' }
            & wsl --set-default-version 2
        }
        else { & wsl --install --no-distribution }
        if ($LASTEXITCODE -ne 0) { throw 'WSL2 did not switch on. Check the message above, then run this script again as administrator.' }
    }
}
if (-not (Has-Tool docker)) { Install-Package 'Docker' docker 'Docker.DockerDesktop' }
if (-not $Check) {
    $env:PATH += ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                 [Environment]::GetEnvironmentVariable('Path', 'User')
}
if (Has-Tool docker) {
    $dockerReady = $false
    $ErrorActionPreference = 'Continue'
    try {
        & docker info >$null 2>$null
        $dockerReady = $LASTEXITCODE -eq 0
    } catch { $dockerReady = $false }
    finally { $ErrorActionPreference = 'Stop' }
    if (-not $dockerReady) {
        Write-Output 'Start Docker Desktop, wait until it is running, then run this script again.'
    } elseif (-not $Check) { Write-Output 'Docker is ready.' }
}

$forgeReady = (Has-Tool forge) -and ((& forge --version 2>$null) -eq "forge v$ForgeVersion")
if (-not $forgeReady) {
    if ($Check) { Missing 'Forge' }
    else {
        Write-Output 'Installing Forge...'
        & uv tool install --force "git+https://github.com/knacklabs/symphony-forge@v$ForgeVersion"
        if ($LASTEXITCODE -ne 0) { throw 'Forge did not install. Check the message above, then run this script again.' }
        & uv tool update-shell
        if ($LASTEXITCODE -ne 0) { throw 'Forge is installed, but its command could not be added to your PATH. Run uv tool update-shell, then open a new PowerShell window.' }
        $toolBin = (& uv tool dir --bin).Trim()
        if ($LASTEXITCODE -ne 0) { throw 'Forge is installed, but its command directory could not be found. Run uv tool update-shell, then open a new PowerShell window.' }
        $env:PATH = "$toolBin;$env:PATH"
    }
} elseif (-not $Check) { Write-Output 'Forge is ready.' }

foreach ($tool in @(@('claude', 'Claude Code', '@anthropic-ai/claude-code'),
                    @('codex', 'Codex', '@openai/codex'))) {
    if (Has-Tool $tool[0]) {
        if (-not $Check) { Write-Output "$($tool[1]) is ready." }
        continue
    }
    if ($Check) { Missing $tool[1]; continue }
    Write-Output "Installing $($tool[1])..."
    & npm.cmd install -g $tool[2]
    if ($LASTEXITCODE -ne 0) { throw "$($tool[1]) did not install. Check the message above, then run this script again." }
}

if (Browsers-Present) {
    if (-not $Check) { Write-Output 'Playwright browsers are ready.' }
}
elseif ($Check) { Missing 'Playwright browsers' }
else {
    Write-Output 'Installing Playwright browsers...'
    & npx.cmd --yes playwright install chromium firefox webkit
    if ($LASTEXITCODE -ne 0) { throw 'Playwright browsers did not install. Check the message above, then run this script again.' }
}

if (-not $Check) {
    Write-Output 'Setup finished. Forge version:'
    & forge --version
    Write-Output 'Next: Open a new PowerShell window, sign in with claude.cmd or codex.cmd, then open your new repo.'
}
