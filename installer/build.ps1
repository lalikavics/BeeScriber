# Builds the BeeScriber installer on Windows (locally or in GitHub Actions).
#   powershell -ExecutionPolicy Bypass -File installer\build.ps1
# Needs: internet, Inno Setup 6 (ISCC.exe) and the C# compiler that comes with Windows (.NET Framework 4).
# Result: build\BeeScriber-<version>-setup.exe
param([string]$PythonVersion = "3.12.10")
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$root  = Split-Path $PSScriptRoot -Parent
$build = Join-Path $root "build"
$dist  = Join-Path $build "dist"
$py    = Join-Path $dist "python"
$ver   = (Select-String -Path "$root\app\beescriber\config.py" -Pattern '^VERSION = "(.+)"').Matches[0].Groups[1].Value
Write-Host "BeeScriber $ver - Python $PythonVersion"

if (Test-Path $build) { Remove-Item -Recurse -Force $build }
New-Item -ItemType Directory -Force $py | Out-Null

# 1. embeddable Python (no installation, nothing in the registry)
Invoke-WebRequest "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip" -OutFile "$build\python.zip"
Expand-Archive "$build\python.zip" $py
$pth = Get-ChildItem $py -Filter "python3*._pth" | Select-Object -First 1
$zip = ($pth.BaseName) + ".zip"
# the app folder is on the path, site-packages are enabled (needed by pip)
[IO.File]::WriteAllText($pth.FullName, "$zip`r`n.`r`nLib\site-packages`r`n..\app`r`nimport site`r`n")

# 2. pip + the packages
Invoke-WebRequest "https://bootstrap.pypa.io/get-pip.py" -OutFile "$build\get-pip.py"
& "$py\python.exe" "$build\get-pip.py" --no-warn-script-location
if ($LASTEXITCODE) { throw "get-pip failed" }
# a few dependencies are source-only (e.g. proxy_tools); the embedded Python cannot use pip's isolated build
# environment (its ._pth file fixes sys.path), so the build tools are installed first and isolation is turned off
& "$py\python.exe" -m pip install --no-warn-script-location --disable-pip-version-check setuptools wheel
if ($LASTEXITCODE) { throw "pip install setuptools failed" }
& "$py\python.exe" -m pip install --no-warn-script-location --disable-pip-version-check --no-build-isolation -r "$PSScriptRoot\requirements.txt"
if ($LASTEXITCODE) { throw "pip install failed" }

# 3. Microsoft C++ runtime DLLs used by CTranslate2 / onnxruntime (in case the PC has no VC++ redistributable)
foreach ($d in "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll", "vcomp140.dll", "concrt140.dll") {
    $src = Join-Path "$env:WINDIR\System32" $d
    if ((Test-Path $src) -and -not (Test-Path (Join-Path $py $d))) { Copy-Item $src $py }
}

# 4. the program
New-Item -ItemType Directory -Force "$dist\app" | Out-Null
Copy-Item -Recurse "$root\app\beescriber" "$dist\app\beescriber"
Get-ChildItem "$dist\app" -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
& "$py\python.exe" -m compileall -q "$dist\app\beescriber" | Out-Null
Copy-Item "$root\LICENSE", "$root\README.md", "$root\CHANGELOG.md" $dist

# 5. BeeScriber.exe (starts python\pythonw.exe -m beescriber without a console window)
$csc = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) { $csc = "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe" }
& $csc /nologo /target:winexe /optimize+ "/out:$dist\BeeScriber.exe" "/win32icon:$root\app\beescriber\ui\logo.ico" `
    /r:System.Windows.Forms.dll "$root\launcher\BeeScriberLauncher.cs"
if ($LASTEXITCODE) { throw "launcher build failed" }

# 6. quick check: the bundled Python can import everything
& "$py\python.exe" -c "import faster_whisper, ctranslate2, webview, reportlab, docx, beescriber.config as c; print('ok', c.APP_NAME, c.VERSION)"
if ($LASTEXITCODE) { throw "import check failed" }

# 7. installer
$iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $iscc) { $iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
& $iscc /Q "/DAppVersion=$ver" "/DSrc=$dist" "/DRoot=$root" "/O$build" "$PSScriptRoot\BeeScriber.iss"
if ($LASTEXITCODE) { throw "Inno Setup failed" }
Get-ChildItem "$build\*.exe" | ForEach-Object { Write-Host ("{0}  {1:N1} MB" -f $_.Name, ($_.Length / 1MB)) }
