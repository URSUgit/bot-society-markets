param(
    [string]$RootUrl = "https://bitprivat.com",
    [string]$ApiUrl = "https://api.bitprivat.com",
    [string]$StatusUrl = "https://status.bitprivat.com",
    [switch]$ExpectOperatorStrip
)

$ErrorActionPreference = "Stop"

function Invoke-ProductionCheck {
    param(
        [string]$Name,
        [string]$Url,
        [scriptblock]$Assert
    )

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 30
        $passed = & $Assert $response
        [pscustomobject]@{
            Name = $Name
            Status = [int]$response.StatusCode
            Passed = [bool]$passed
            Bytes = $response.Content.Length
            Url = $Url
        }
    } catch {
        [pscustomobject]@{
            Name = $Name
            Status = "ERR"
            Passed = $false
            Bytes = 0
            Url = $Url
            Error = $_.Exception.Message
        }
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

$results = foreach ($check in $checks) {
    Invoke-ProductionCheck -Name $check.Name -Url $check.Url -Assert $check.Assert
}

$results | Format-Table -AutoSize

if ($results.Passed -contains $false) {
    throw "Production verification failed. See failed checks above."
}

Write-Output "Production verification passed."
