# Check and generate REDIS_PASSWORD if not set
if (-not $env:REDIS_PASSWORD) {
    $env:REDIS_PASSWORD = [Convert]::ToBase64String(
        [System.Security.Cryptography.RandomNumberGenerator]::GetBytes(36)
    ) -replace '=', ''
}

# Check and generate AUTHENTIK_SECRET_KEY if not set
if (-not $env:AUTHENTIK_SECRET_KEY) {
    $env:AUTHENTIK_SECRET_KEY = [Convert]::ToBase64String(
        [System.Security.Cryptography.RandomNumberGenerator]::GetBytes(60)
    ) -replace '=', ''
}

# Get command (server/worker)
$command = $args[0]

if ($command -eq "server") {
    /authentik/entrypoint.sh server
} elseif ($command -eq "worker") {
    /authentik/entrypoint.sh worker
} else {
    Write-Error "Unknown command: $command"
    exit 1
}
