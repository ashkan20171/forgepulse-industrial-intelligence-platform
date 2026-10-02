Set-Location (Join-Path $PSScriptRoot 'backend')
if (-not (Test-Path '.venv')) { py -m venv .venv }
& .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:POSTGRES_URL='sqlite:///./forgepulse-local.db'
$env:MQTT_ENABLED='false'
$env:CORS_ORIGINS='http://localhost:8000,http://127.0.0.1:8000,null'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
