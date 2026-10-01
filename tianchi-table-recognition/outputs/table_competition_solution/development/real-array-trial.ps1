param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ForwardArgs)
$ErrorActionPreference = 'Stop'
$trialDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$trialProject = Split-Path -Parent $trialDirectory
$nodeExe = 'C:\Users\zhhzh\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
$previousApiKey = $env:DASHSCOPE_API_KEY
$previousBaseUrl = $env:ALIYUN_BASE_URL
$storedCredential = $null
$credentialPointer = [IntPtr]::Zero
$runnerExitCode = 1
try {
    if ($ForwardArgs -contains '--allow-paid' -and $ForwardArgs -notcontains '--dry-run' -and
        $ForwardArgs -notcontains '--write-plan' -and [string]::IsNullOrWhiteSpace($env:DASHSCOPE_API_KEY)) {
        Import-Module (Join-Path $trialProject 'credential-store.psm1') -Force
        if ((Get-TianchiCredentialStatus).Exists) {
            $storedCredential = Read-TianchiStoredCredential
            $credentialPointer = [Runtime.InteropServices.Marshal]::SecureStringToGlobalAllocUnicode($storedCredential.SecureKey)
            $env:DASHSCOPE_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringUni($credentialPointer)
            [Runtime.InteropServices.Marshal]::ZeroFreeGlobalAllocUnicode($credentialPointer)
            $credentialPointer = [IntPtr]::Zero
            if ([string]::IsNullOrWhiteSpace($env:ALIYUN_BASE_URL) -and [string]::IsNullOrWhiteSpace($env:ALIYUN_WORKSPACE_ID)) {
                $env:ALIYUN_BASE_URL = $storedCredential.BaseUrl
            }
            Write-Output '[CREDENTIAL] Windows-encrypted credential loaded for this process; secret not displayed.'
        }
    }
    & $nodeExe (Join-Path $trialDirectory 'real-array-trial.mjs') @ForwardArgs
    $runnerExitCode = $LASTEXITCODE
} finally {
    $env:DASHSCOPE_API_KEY = $previousApiKey
    $env:ALIYUN_BASE_URL = $previousBaseUrl
    if ($credentialPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeGlobalAllocUnicode($credentialPointer) }
    if ($storedCredential) { $storedCredential.SecureKey.Dispose() }
    $previousApiKey = $null; $storedCredential = $null
}
exit $runnerExitCode
