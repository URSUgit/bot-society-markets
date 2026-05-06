param(
    [string]$ApiBaseUrl = "https://console-api.akash.network",
    [string]$ApiKey = $env:AKASH_API_KEY,
    [string]$Dseq,
    [string]$SdlPath,
    [switch]$List,
    [switch]$CreateNew,
    [decimal]$DepositUsd = 5,
    [int]$BidWaitSeconds = 30
)

$ErrorActionPreference = "Stop"

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

    if ($null -ne $Body) {
        $json = $Body | ConvertTo-Json -Depth 100
        Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers -ContentType "application/json" -Body $json
    } else {
        Invoke-RestMethod -Method $Method -Uri $uri -Headers $headers
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
    return
}

if (-not $Dseq) {
    throw "Pass -Dseq for the existing deployment to update. Use -List to find active DSEQ values."
}

Invoke-AkashConsoleApi -Method "PUT" -Path "/v1/deployments/$Dseq" -Body @{
    data = @{
        sdl = $sdl
    }
} | Out-Null

Write-Output "Updated Akash deployment $Dseq with SDL: $SdlPath"
Write-Output "Wait for the new pod to start, then run deploy\verify-production.ps1 -ExpectOperatorStrip -ExpectSocialTrading"
