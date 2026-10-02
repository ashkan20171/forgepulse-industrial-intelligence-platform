@echo off
setlocal
cd /d "%~dp0backend"
if not exist .venv (
  py -m venv .venv
)
call .venv\Scripts\activate
python -m pip install -r requirements.txt
set POSTGRES_URL=sqlite:///./forgepulse-local.db
set MQTT_ENABLED=false
set CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,null
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
