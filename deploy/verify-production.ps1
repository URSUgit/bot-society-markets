param(
    [string]$RootUrl = "https://bitprivat.com",
    [string]$AppUrl = "https://app.bitprivat.com",
    [string]$ApiUrl = "https://api.bitprivat.com",
    [string]$StatusUrl = "https://status.bitprivat.com",
    [int]$Attempts = 3,
    [int]$RetryDelaySeconds = 2,
    [switch]$ExpectOperatorStrip,
    [switch]$ExpectSocialTrading,
    [switch]$RequireLiveOrigin,
    [switch]$CheckDirectOrigin
)

$ErrorActionPreference = "Stop"

function Get-ResponseHeader {
    param(
        $Response,
        [string]$Name
    )

    $value = $Response.Headers[$Name]
    if ($null -eq $value) {
        return ""
    }
    if ($value -is [array]) {
        return ($value -join ",")
    }
    return [string]$value
}

function Add-QueryFlag {
    param(
        [string]$Url,
        [string]$Name,
        [string]$Value = "1"
    )

    $separator = if ($Url.Contains("?")) { "&" } else { "?" }
    return "$Url$separator$Name=$Value"
}

function Invoke-ProductionCheck {
    param(
        [string]$Name,
        [string]$Url,
        [scriptblock]$Assert,
        [bool]$RequireLive = $false
    )

    $lastError = $null
    for ($attempt = 1; $attempt -le [Math]::Max(1, $Attempts); $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 30
            $passed = & $Assert $response
            $deliveryMode = Get-ResponseHeader -Response $response -Name "X-BITprivat-Data-Mode"
            if ($RequireLive -and @("edge-fallback", "edge-snapshot", "origin-unavailable", "origin-probe-failed") -contains $deliveryMode) {
                $passed = $false
            }
            if ($passed -or $attempt -ge $Attempts) {
                return [pscustomobject]@{
                    Name = $Name
                    Status = [int]$response.StatusCode
                    Passed = [bool]$passed
                    Bytes = $response.Content.Length
                    DataMode = $deliveryMode
                    OriginStatus = Get-ResponseHeader -Response $response -Name "X-BITprivat-Origin-Status"
                    FallbackReason = Get-ResponseHeader -Response $response -Name "X-BITprivat-Fallback-Reason"
                    Url = $Url
                    Attempts = $attempt
                }
            }
        } catch {
            $lastError = $_.Exception.Message
            if ($attempt -ge $Attempts) {
                return [pscustomobject]@{
                    Name = $Name
                    Status = "ERR"
                    Passed = $false
                    Bytes = 0
                    Url = $Url
                    Attempts = $attempt
                    Error = $lastError
                }
            }
        }

        Start-Sleep -Seconds ([Math]::Max(1, $RetryDelaySeconds) * $attempt)
    }

    [pscustomobject]@{
        Name = $Name
        Status = "ERR"
        Passed = $false
        Bytes = 0
        Url = $Url
        Attempts = [Math]::Max(1, $Attempts)
        Error = if ($lastError) { $lastError } else { "Unknown verification failure." }
    }
}

$cacheBust = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$checks = @(
    @{
        Name = "Landing"
        Url = "$RootUrl/?v=$cacheBust"
        Assert = { param($r) $r.StatusCode -eq 200 -and $r.Content -like "*BITprivat*" }
    },
    @{
        Name = "Dashboard shell"
        Url = "$RootUrl/dashboard?v=$cacheBust"
        Assert = { param($r) $r.StatusCode -eq 200 -and $r.Content -like "*market-console-section*" }
    },
    @{
        Name = "App dashboard"
        Url = "$AppUrl/?v=$cacheBust"
        Assert = { param($r) $r.StatusCode -eq 200 -and $r.Content -like "*market-console-section*" -and $r.Content -like "*trader-intelligence-section*" }
    },
    @{
        Name = "API pulse"
        Url = "$ApiUrl/api/v1/system/pulse?v=$cacheBust"
        RequireLive = $true
        Assert = { param($r) $r.StatusCode -eq 200 -and $r.Content -like "*system_pulse*" }
    },
    @{
        Name = "Status page"
        Url = "$StatusUrl/?v=$cacheBust"
        Assert = { param($r) $r.StatusCode -eq 200 -and $r.Content -like "*System*" }
    }
)

if ($ExpectOperatorStrip) {
    $checks += @{
        Name = "Dashboard operator strip"
        Url = "$RootUrl/dashboard?v=$cacheBust"
        Assert = { param($r) $r.StatusCode -eq 200 -and $r.Content -like "*operator-strip*" }
    }
}

if ($ExpectSocialTrading) {
    $checks += @(
        @{
            Name = "Social trading API"
            Url = "$ApiUrl/api/social-trading?v=$cacheBust"
            RequireLive = $true
            Assert = { param($r) $r.StatusCode -eq 200 -and $r.Content -like "*top_traders*" -and $r.Content -like "*safety_notes*" }
        },
        @{
            Name = "Social traders API"
            Url = "$ApiUrl/api/social-traders?v=$cacheBust"
            RequireLive = $true
            Assert = { param($r) $r.StatusCode -eq 200 -and $r.Content -like "*display_name*" -and $r.Content -like "*composite_score*" }
        },
        @{
            Name = "Dashboard social section"
            Url = "$RootUrl/dashboard?v=$cacheBust"
            Assert = { param($r) $r.StatusCode -eq 200 -and $r.Content -like "*social-trader-section*" -and ($r.Content -like "*Run YouTube Discovery*" -or $r.Content -like "*Scan New Videos*") }
        }
    )
}

if ($CheckDirectOrigin) {
    $runtimeUrl = "$RootUrl/api/runtime/public-origin?v=$cacheBust"
    $runtime = Invoke-RestMethod -Uri $runtimeUrl -TimeoutSec 30
    if (-not $runtime.social_read_origin) {
        throw "Could not resolve social_read_origin from $runtimeUrl."
    }
    $origin = ([string]$runtime.social_read_origin).TrimEnd("/")
    $checks += @(
        @{
            Name = "Direct origin pulse"
            Url = "$origin/api/v1/system/pulse?v=$cacheBust"
            Assert = { param($r) $r.StatusCode -eq 200 -and $r.Content -like "*system_pulse*" }
        },
        @{
            Name = "Direct origin social"
            Url = "$origin/api/social-trading?v=$cacheBust"
            Assert = { param($r) $r.StatusCode -eq 200 -and $r.Content -like "*top_traders*" -and $r.Content -like "*safety_notes*" }
        }
    )
}

$results = foreach ($check in $checks) {
    $url = $check.Url
    $strictLive = [bool]($RequireLiveOrigin -and $check.RequireLive)
    if ($strictLive) {
        $url = Add-QueryFlag -Url (Add-QueryFlag -Url $url -Name "fresh" -Value "1") -Name "edge_require_live" -Value "1"
    }
    Invoke-ProductionCheck -Name $check.Name -Url $url -Assert $check.Assert -RequireLive:$strictLive
}

$results | Format-Table -AutoSize

if ($results.Passed -contains $false) {
    throw "Production verification failed. See failed checks above."
}

Write-Output "Production verification passed."
