# Windows PowerShell script to run the backend from any location.
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
