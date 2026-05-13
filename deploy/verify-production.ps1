param(
    [string]$RootUrl = "https://bitprivat.com",
    [string]$ApiUrl = "https://api.bitprivat.com",
    [string]$StatusUrl = "https://status.bitprivat.com",
    [int]$Attempts = 3,
    [int]$RetryDelaySeconds = 2,
    [switch]$ExpectOperatorStrip,
    [switch]$ExpectSocialTrading
)

$ErrorActionPreference = "Stop"

function Invoke-ProductionCheck {
    param(
        [string]$Name,
        [string]$Url,
        [scriptblock]$Assert
    )

    $lastError = $null
    for ($attempt = 1; $attempt -le [Math]::Max(1, $Attempts); $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 30
            $passed = & $Assert $response
            if ($passed -or $attempt -ge $Attempts) {
                return [pscustomobject]@{
                    Name = $Name
                    Status = [int]$response.StatusCode
                    Passed = [bool]$passed
                    Bytes = $response.Content.Length
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
        Name = "API pulse"
        Url = "$ApiUrl/api/v1/system/pulse?v=$cacheBust"
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
            Assert = { param($r) $r.StatusCode -eq 200 -and $r.Content -like "*top_traders*" -and $r.Content -like "*safety_notes*" }
        },
        @{
            Name = "Social traders API"
            Url = "$ApiUrl/api/social-traders?v=$cacheBust"
            Assert = { param($r) $r.StatusCode -eq 200 -and $r.Content -like "*display_name*" -and $r.Content -like "*composite_score*" }
        },
        @{
            Name = "Dashboard social section"
            Url = "$RootUrl/dashboard?v=$cacheBust"
            Assert = { param($r) $r.StatusCode -eq 200 -and $r.Content -like "*social-trader-section*" -and $r.Content -like "*Run YouTube Discovery*" }
        }
    )
}

$results = foreach ($check in $checks) {
    Invoke-ProductionCheck -Name $check.Name -Url $check.Url -Assert $check.Assert
}

$results | Format-Table -AutoSize

if ($results.Passed -contains $false) {
    throw "Production verification failed. See failed checks above."
}

Write-Output "Production verification passed."
