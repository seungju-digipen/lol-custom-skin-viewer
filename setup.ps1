$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 이상을 설치해주세요.' }
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Python 의존성 설치 실패' }
New-Item -ItemType Directory -Path tools -Force | Out-Null
Invoke-WebRequest 'https://github.com/Crauzer/lol2gltf/releases/download/2025-02-28-d36a532/lol2gltf.exe' -OutFile 'tools/lol2gltf.exe'
Invoke-WebRequest 'https://github.com/LeagueToolkit/wadtools/releases/download/v0.5.7/wadtools-0.5.7-windows-x64.zip' -OutFile 'tools/wadtools.zip'
Expand-Archive -LiteralPath 'tools/wadtools.zip' -DestinationPath 'tools/wadtools' -Force
Invoke-WebRequest 'https://github.com/LeagueToolkit/ltk-tex-utils/releases/download/v0.3.0/ltk-tex-utils-windows.exe' -OutFile 'tools/ltk-tex-utils.exe'
Invoke-WebRequest 'https://github.com/moonshadow565/ritobin/releases/download/2026-09-20-368b413/ritobin.zip' -OutFile 'tools/ritobin.zip'
Expand-Archive -LiteralPath 'tools/ritobin.zip' -DestinationPath 'tools/ritobin' -Force
$metadata = Invoke-RestMethod 'https://dotnetcli.blob.core.windows.net/dotnet/release-metadata/8.0/releases.json'
$runtimeFile = $metadata.releases[0].runtime.files | Where-Object { $_.rid -eq 'win-x64' -and $_.name -like '*.zip' } | Select-Object -First 1
Invoke-WebRequest $runtimeFile.url -OutFile 'tools/runtime.zip'
Expand-Archive -LiteralPath 'tools/runtime.zip' -DestinationPath 'tools/dotnet' -Force
& '.\tools\wadtools\wadtools.exe' --hashtable-dir '.\tools\hashes' download-hashes
if ($LASTEXITCODE -ne 0) { throw '해시 목록 다운로드 실패' }
if (-not (Test-Path -LiteralPath 'config.json')) { Copy-Item -LiteralPath 'config.example.json' -Destination 'config.json' }
Write-Host 'config.json의 champions_dir을 롤 설치 경로로 변경한 뒤 start.cmd를 실행하세요.'
