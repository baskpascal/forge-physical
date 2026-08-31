[CmdletBinding()]
param(
    [string]$Project = "supple-voyage-507119-v0",
    [string]$Region = "us-central1",
    [string]$Job = "forge-worker",
    [string]$ApiUrl = "https://forge-api-rldj6ghw7q-uc.a.run.app",
    [int]$TimeoutSeconds = 300,
    [int]$MaxPostSeconds = 10,
    [int]$MaxBuildSeconds = 240
)

$ErrorActionPreference = "Stop"
$terminalStatuses = @("completed", "needs_review", "failed", "unsupported_scope")
$injectionVariable = "INJECT_COMPILE_FAILURE_ONCE"
$jobWasChanged = $false
$previousInjectionValue = $null

function Invoke-Gcloud {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & gcloud @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "gcloud failed: gcloud $($Arguments -join ' ')"
    }
}

if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    throw "gcloud CLI is required. Authenticate an account with access to '$Project'."
}

$ApiUrl = $ApiUrl.TrimEnd("/")
Invoke-Gcloud projects describe $Project '--format=value(projectId)' | Out-Null

$jobJson = Invoke-Gcloud run jobs describe $Job --project=$Project --region=$Region --format=json |
    ConvertFrom-Json
$container = $jobJson.spec.template.spec.template.spec.containers | Select-Object -First 1
$existingInjection = $container.env | Where-Object { $_.name -eq $injectionVariable } |
    Select-Object -First 1
if ($existingInjection) {
    if (-not $existingInjection.PSObject.Properties["value"]) {
        throw "$injectionVariable already exists but is not a plain value; refusing to overwrite it."
    }
    $previousInjectionValue = [string]$existingInjection.value
}

try {
    Write-Host "Enabling one intentional compiler failure on the worker job..."
    $enableArguments = @(
        "run", "jobs", "update", $Job, "--project=$Project", "--region=$Region", "--quiet",
        "--update-env-vars=$injectionVariable=true"
    )
    Invoke-Gcloud @enableArguments | Out-Null
    $jobWasChanged = $true

    $prompt = @{
        prompt = "Create an ESP32 temperature alarm. Use a temperature sensor. Turn the warning LED on when temperature is above 30 degrees Celsius. The design must be testable automatically in Wokwi."
    } | ConvertTo-Json

    $postTimer = [Diagnostics.Stopwatch]::StartNew()
    $requestArguments = @{
        Method = "Post"
        Uri = "$ApiUrl/api/builds"
        ContentType = "application/json"
        Body = $prompt
    }
    $created = Invoke-RestMethod @requestArguments
    $postTimer.Stop()
    if (-not $created.build_id) { throw "The API did not return a build_id." }
    if ($postTimer.Elapsed.TotalSeconds -gt $MaxPostSeconds) {
        throw "POST /api/builds took $([math]::Round($postTimer.Elapsed.TotalSeconds, 2))s; target is at most ${MaxPostSeconds}s."
    }

    Write-Host "Build $($created.build_id) accepted in $($postTimer.ElapsedMilliseconds) ms."
    Write-Host $created.build_url
    $buildTimer = [Diagnostics.Stopwatch]::StartNew()
    $deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        Start-Sleep -Seconds 5
        $result = Invoke-RestMethod -Method Get -Uri "$ApiUrl/api/builds/$($created.build_id)"
        Write-Host ("{0,3}%  {1,-14} {2}" -f $result.progress, $result.status, $result.stage)
    } while ($terminalStatuses -notcontains [string]$result.status -and
        [DateTimeOffset]::UtcNow -lt $deadline)
    $buildTimer.Stop()

    if ($terminalStatuses -notcontains [string]$result.status) {
        throw "Build did not reach a terminal state within ${TimeoutSeconds}s."
    }

    $eventTypes = @($result.events | ForEach-Object { $_.type })
    $repairEvent = $result.events | Where-Object {
        $_.type -eq "agent.repair.started" -and $_.metadata.agent -eq "EngineeringAgent"
    } | Select-Object -First 1
    $requiredEvents = @("firmware.compile.failed", "agent.repair.started", "firmware.compile.passed")
    $missingEvents = @($requiredEvents | Where-Object { $eventTypes -notcontains $_ })

    if ($missingEvents.Count -gt 0) {
        throw "Missing repair evidence events: $($missingEvents -join ', ')."
    }
    if (-not $repairEvent) {
        throw "The repair event did not identify EngineeringAgent; inspect the build before claiming agent repair."
    }
    if (@($eventTypes | Where-Object { $_ -eq "firmware.compile.started" }).Count -lt 2) {
        throw "The event stream does not prove a bounded recompile after repair."
    }
    if ($result.firmware.status -ne "passed") { throw "Firmware did not pass after repair." }
    if ($result.simulation.status -ne "passed") { throw "Wokwi simulation did not pass." }
    if ($result.status -ne "completed") { throw "Build ended as '$($result.status)', not 'completed'." }
    if ($buildTimer.Elapsed.TotalSeconds -gt $MaxBuildSeconds) {
        throw "Golden build took $([math]::Round($buildTimer.Elapsed.TotalSeconds, 2))s; target is at most ${MaxBuildSeconds}s."
    }

    [pscustomobject]@{
        build_id = $created.build_id
        build_url = $created.build_url
        post_ms = $postTimer.ElapsedMilliseconds
        build_seconds = [math]::Round($buildTimer.Elapsed.TotalSeconds, 2)
        repair_agent = $repairEvent.metadata.agent
        firmware = $result.firmware.status
        simulation = $result.simulation.status
        status = $result.status
    } | Format-List
}
finally {
    if ($jobWasChanged) {
        Write-Host "Restoring the worker job configuration..."
        if ($null -ne $previousInjectionValue) {
            $restoreArguments = @(
                "run", "jobs", "update", $Job, "--project=$Project", "--region=$Region", "--quiet",
                "--update-env-vars=$injectionVariable=$previousInjectionValue"
            )
            Invoke-Gcloud @restoreArguments | Out-Null
        }
        else {
            $restoreArguments = @(
                "run", "jobs", "update", $Job, "--project=$Project", "--region=$Region", "--quiet",
                "--remove-env-vars=$injectionVariable"
            )
            Invoke-Gcloud @restoreArguments | Out-Null
        }
    }
}
