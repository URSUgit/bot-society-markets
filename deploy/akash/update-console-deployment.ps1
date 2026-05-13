param(
    [string]$ApiBaseUrl = "https://console-api.akash.network",
    [string]$ApiKey = $env:AKASH_API_KEY,
    [string]$Dseq,
    [string]$SdlPath,
    [switch]$List,
    [switch]$CreateNew,
    [decimal]$DepositUsd = 5,
    [int]$BidWaitSeconds = 30,
    [int]$WaitSeconds = 90,
    [switch]$Verify,
    [string]$RootUrl = "https://bitprivat.com",
    [string]$ApiUrl = "https://api.bitprivat.com",
    [string]$StatusUrl = "https://status.bitprivat.com",
    [int]$ApiMaxAttempts = 6,
    [int]$ApiRetryBaseSeconds = 5,
    [switch]$ExpectOperatorStrip,
    [switch]$ExpectSocialTrading
)

$ErrorActionPreference = "Stop"

function Test-TransientAkashError {
    param([Parameter(Mandatory = $true)]$ErrorRecord)

    $messageParts = @(
        $ErrorRecord.Exception.Message
        $ErrorRecord.ErrorDetails.Message
    ) | Where-Object { $_ }
    $message = $messageParts -join " "

    $statusCode = $null
    if ($ErrorRecord.Exception.Response -and $ErrorRecord.Exception.Response.StatusCode) {
        $statusCode = [int]$ErrorRecord.Exception.Response.StatusCode
    }

    if ($statusCode -in @(408, 429, 500, 502, 503, 504)) {
        return $true
    }

    return $message -match "ServiceUnavailableError|service_unavailable|temporarily unavailable|timeout|timed out|gateway|connection reset|connection.*closed"
}

function Invoke-AkashConsoleApi {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Method,
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [object]$Body
    )

    if (-not $ApiKey) {
        throw "AKASH_API_KEY is not set. Set it in this PowerShell session before running this script."
    }

    $headers = @{
        "x-api-key" = $ApiKey
    }
    $uri = "$ApiBaseUrl$Path"
    $canRetrySafely = $Method -in @("GET", "PUT")
    $attempts = if ($canRetrySafely) { [Math]::Max(1, $ApiMaxAttempts) } else { 1 }

    for ($attempt = 1; $attempt -le $attempts; $attempt++) {
        try {
            if ($null -ne $Body) {
                $json = $Body | ConvertTo-Json -Depth 100
                return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers -ContentType "application/json" -Body $json
            }

            return Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers
        } catch {
            $isTransient = Test-TransientAkashError -ErrorRecord $_
            if (-not $canRetrySafely -or -not $isTransient -or $attempt -ge $attempts) {
                throw
            }

            $delay = [int][Math]::Min(60, $ApiRetryBaseSeconds * [Math]::Pow(2, $attempt - 1))
            Write-Output "Akash Console API $Method $Path failed with a transient provider error (attempt $attempt/$attempts). Retrying in $delay seconds..."
            Start-Sleep -Seconds $delay
        }
    }
}

function Get-SdlContent {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolvedPath = if ([System.IO.Path]::IsPathRooted($Path)) {
        $Path
    } else {
        Join-Path (Get-Location) $Path
    }

    if (-not (Test-Path -LiteralPath $resolvedPath)) {
        throw "SDL file not found: $resolvedPath"
    }

    Get-Content -LiteralPath $resolvedPath -Raw
}

function Invoke-ProductionVerification {
    $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $verifyScript = Join-Path $repoRoot "deploy\verify-production.ps1"
    if (-not (Test-Path -LiteralPath $verifyScript)) {
        throw "Production verifier not found: $verifyScript"
    }

    $verifyArgs = @{
        RootUrl = $RootUrl
        ApiUrl = $ApiUrl
        StatusUrl = $StatusUrl
    }
    if ($ExpectOperatorStrip) {
        $verifyArgs.ExpectOperatorStrip = $true
    }
    if ($ExpectSocialTrading) {
        $verifyArgs.ExpectSocialTrading = $true
    }

    & $verifyScript @verifyArgs
}

function Wait-AfterDeploymentUpdate {
    param([string]$ActiveDseq)

    if ($WaitSeconds -le 0) {
        return
    }

    Write-Output "Waiting $WaitSeconds seconds for Akash provider rollout..."
    Start-Sleep -Seconds $WaitSeconds

    try {
        $deployment = Invoke-AkashConsoleApi -Method "GET" -Path "/v1/deployments/$ActiveDseq"
        $leases = @($deployment.data.leases)
        $uris = @()
        foreach ($lease in $leases) {
            if ($lease.status -and $lease.status.services) {
                $uris += $lease.status.services.PSObject.Properties.Value | ForEach-Object { $_.uris }
            }
        }
        if ($uris.Count) {
            Write-Output "Akash lease URIs: $($uris -join ', ')"
        }
    } catch {
        Write-Output "Akash deployment status check skipped after update: $($_.Exception.Message)"
    }
}

if ($List) {
    $response = Invoke-AkashConsoleApi -Method "GET" -Path "/v1/deployments?skip=0&limit=100"
    $deployments = @($response.data.deployments)
    if (-not $deployments.Count) {
        Write-Output "No deployments found for this Akash Console API key."
        return
    }

    $deployments | ForEach-Object {
        $deployment = $_.deployment
        $lease = @($_.leases) | Select-Object -First 1
        [pscustomobject]@{
            Dseq = $deployment.id.dseq
            State = $deployment.state
            Provider = if ($lease) { $lease.id.provider } else { "" }
            Price = if ($lease) { "$($lease.price.amount) $($lease.price.denom)" } else { "" }
            Uris = if ($lease -and $lease.status -and $lease.status.services) {
                ($lease.status.services.PSObject.Properties.Value | ForEach-Object { $_.uris }) -join ", "
            } else {
                ""
            }
        }
    } | Format-Table -AutoSize
    return
}

if (-not $SdlPath) {
    throw "Pass -SdlPath to the Akash SDL file, or use -List to discover existing deployments."
}

$sdl = Get-SdlContent -Path $SdlPath

if ($CreateNew) {
    $created = Invoke-AkashConsoleApi -Method "POST" -Path "/v1/deployments" -Body @{
        data = @{
            sdl = $sdl
            deposit = $DepositUsd
        }
    }

    $createdDseq = $created.data.dseq
    $manifest = $created.data.manifest
    Write-Output "Created deployment DSEQ: $createdDseq"
    Write-Output "Waiting $BidWaitSeconds seconds for provider bids..."
    Start-Sleep -Seconds $BidWaitSeconds

    $bids = Invoke-AkashConsoleApi -Method "GET" -Path "/v1/bids?dseq=$createdDseq"
    $firstBid = @($bids.data) | Select-Object -First 1
    if (-not $firstBid) {
        throw "No provider bids returned for deployment $createdDseq."
    }

    $bidId = $firstBid.bid.id
    Invoke-AkashConsoleApi -Method "POST" -Path "/v1/leases" -Body @{
        manifest = $manifest
        leases = @(
            @{
                dseq = $createdDseq
                gseq = $bidId.gseq
                oseq = $bidId.oseq
                provider = $bidId.provider
            }
        )
    } | Out-Null

    Write-Output "Lease created for deployment $createdDseq."
    Invoke-AkashConsoleApi -Method "GET" -Path "/v1/deployments/$createdDseq" | ConvertTo-Json -Depth 20
    Wait-AfterDeploymentUpdate -ActiveDseq $createdDseq
    if ($Verify) {
        Invoke-ProductionVerification
    }
    return
}

if (-not $Dseq) {
    throw "Pass -Dseq for the existing deployment to update. Use -List to find active DSEQ values."
}

try {
    Invoke-AkashConsoleApi -Method "PUT" -Path "/v1/deployments/$Dseq" -Body @{
        data = @{
            sdl = $sdl
        }
    } | Out-Null
} catch {
    $message = $_.Exception.Message
    if ($message -match "404|not_found|NotFound|Deployment not found") {
        throw "Akash deployment '$Dseq' was not found for this API key. Run deploy\akash\deploy-production.ps1 -List, or trigger the Akash Deploy workflow with mode=list, then update AKASH_DSEQ with an active deployment DSEQ."
    }
    throw
}

Write-Output "Updated Akash deployment $Dseq with SDL: $SdlPath"
Wait-AfterDeploymentUpdate -ActiveDseq $Dseq
if ($Verify) {
    Invoke-ProductionVerification
} else {
    Write-Output "Verification skipped. To verify manually, run deploy\verify-production.ps1 -ExpectOperatorStrip -ExpectSocialTrading"
}
