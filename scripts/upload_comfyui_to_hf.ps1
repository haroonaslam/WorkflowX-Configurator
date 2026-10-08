[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[^/\s]+/[^/\s]+$')]
    [string]$RepoId,

    [Parameter()]
    [string]$FolderPath = 'E:\ComfyUI',

    [Parameter()]
    [ValidateRange(1, 32)]
    [int]$Workers = 4,

    [Parameter()]
    [string]$Revision = 'main',

    [Parameter()]
    [switch]$Public,

    [Parameter()]
    [switch]$Yes
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-Hf {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & hf @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Hugging Face CLI failed with exit code ${LASTEXITCODE}: hf $($Arguments -join ' ')"
    }
}

if (-not (Get-Command hf -ErrorAction SilentlyContinue)) {
    throw 'The Hugging Face CLI command "hf" was not found. Install or update huggingface_hub first.'
}

if (-not (Test-Path -LiteralPath $FolderPath -PathType Container)) {
    throw "Upload folder does not exist: $FolderPath"
}
$resolvedFolder = (Resolve-Path -LiteralPath $FolderPath).Path

$files = Get-ChildItem -LiteralPath $resolvedFolder -Recurse -File
if ($files.Count -eq 0) {
    throw "Upload folder contains no files: $resolvedFolder"
}

$totalBytes = ($files | Measure-Object -Property Length -Sum).Sum
$totalGiB = [math]::Round($totalBytes / 1GB, 2)
$visibility = if ($Public) { 'public' } else { 'private' }

Write-Host "Source:     $resolvedFolder"
Write-Host "Repository: $RepoId"
Write-Host "Visibility: $visibility"
Write-Host "Revision:   $Revision"
Write-Host "Files:      $($files.Count)"
Write-Host "Size:       $totalGiB GiB"

if (-not $Yes) {
    $confirmation = Read-Host 'Type UPLOAD to continue'
    if ($confirmation -cne 'UPLOAD') {
        Write-Host 'Upload cancelled.'
        exit 0
    }
}

$hadToken = -not [string]::IsNullOrWhiteSpace($env:HF_TOKEN)
$previousToken = $env:HF_TOKEN

try {
    if (-not $hadToken) {
        $secureToken = Read-Host 'Hugging Face write token' -AsSecureString
        $tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
        try {
            $env:HF_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)
        }
        finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer)
        }
    }

    Invoke-Hf -Arguments @('auth', 'whoami')

    $createArguments = @(
        'repo', 'create', $RepoId,
        '--repo-type', 'model',
        '--exist-ok'
    )
    if (-not $Public) {
        $createArguments += '--private'
    }
    Invoke-Hf -Arguments $createArguments

    $uploadArguments = @(
        'upload-large-folder', $RepoId, $resolvedFolder,
        '--repo-type', 'model',
        '--revision', $Revision,
        '--num-workers', $Workers.ToString()
    )
    if (-not $Public) {
        $uploadArguments += '--private'
    }

    Invoke-Hf -Arguments $uploadArguments
    Write-Host "Upload complete: https://huggingface.co/$RepoId"
}
finally {
    if ($hadToken) {
        $env:HF_TOKEN = $previousToken
    }
    else {
        $env:HF_TOKEN = $null
    }
}
