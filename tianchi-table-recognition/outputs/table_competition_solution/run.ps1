param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ForwardArgs
)

$ErrorActionPreference = 'Stop'
$runtimeRoot = 'C:\Users\zhhzh\.cache\codex-runtimes\codex-primary-runtime\dependencies'
$nodeExe = Join-Path $runtimeRoot 'node\bin\node.exe'
$moduleSource = Join-Path $runtimeRoot 'node\node_modules'
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$moduleLink = Join-Path $projectDir 'node_modules'

if (-not (Test-Path -LiteralPath $nodeExe)) {
    throw "未找到 Codex 内置 Node.js：$nodeExe"
}

if (-not (Test-Path -LiteralPath $moduleLink)) {
    New-Item -ItemType Junction -Path $moduleLink -Target $moduleSource | Out-Null
}

$previousApiKey = $env:DASHSCOPE_API_KEY
$previousBaseUrl = $env:ALIYUN_BASE_URL
$storedCredential = $null
$credentialPointer = [IntPtr]::Zero
$runnerExitCode = 1
try {
    # Dry runs and unapproved runs must not decrypt stored credentials.
    if ($ForwardArgs -contains '--allow-paid' -and $ForwardArgs -notcontains '--dry-run' -and
        [string]::IsNullOrWhiteSpace($env:DASHSCOPE_API_KEY)) {
        Import-Module (Join-Path $projectDir 'credential-store.psm1') -Force
        if ((Get-TianchiCredentialStatus).Exists) {
            $storedCredential = Read-TianchiStoredCredential
            $credentialPointer = [Runtime.InteropServices.Marshal]::SecureStringToGlobalAllocUnicode($storedCredential.SecureKey)
            $env:DASHSCOPE_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringUni($credentialPointer)
            [Runtime.InteropServices.Marshal]::ZeroFreeGlobalAllocUnicode($credentialPointer)
            $credentialPointer = [IntPtr]::Zero
            if ([string]::IsNullOrWhiteSpace($env:ALIYUN_BASE_URL) -and [string]::IsNullOrWhiteSpace($env:ALIYUN_WORKSPACE_ID)) {
                $env:ALIYUN_BASE_URL = $storedCredential.BaseUrl
            }
            Write-Output '[CREDENTIAL] Loaded Windows-encrypted credential for this process; secret not displayed.'
        }
    }
    $runnerFile = if ($ForwardArgs -contains '--structure-review') { 'development\structure-review.mjs' } else { 'run.mjs' }
    & $nodeExe (Join-Path $projectDir $runnerFile) @ForwardArgs
    $runnerExitCode = $LASTEXITCODE
} finally {
    $env:DASHSCOPE_API_KEY = $previousApiKey
    $env:ALIYUN_BASE_URL = $previousBaseUrl
    if ($credentialPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeGlobalAllocUnicode($credentialPointer) }
    if ($storedCredential) { $storedCredential.SecureKey.Dispose() }
    $previousApiKey = $null; $storedCredential = $null
}
exit $runnerExitCode
