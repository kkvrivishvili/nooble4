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

# Start Authentik server
/authentik/entrypoint.sh server
