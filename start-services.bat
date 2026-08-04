@echo off
REM 1M Context Compression Proxy - Windows Quick Start Script

echo ================================
echo 1M Context Compression Proxy
echo Quick Start Script (Windows)
echo ================================
echo.

REM Check .env file
if not exist ".env" (
    echo ❌ .env file not found!
    echo 📝 Creating from .env.example...
    copy .env.example .env
    echo ⚠️  Please edit .env and add your API keys!
    echo.
    echo Required variables:
    echo   - EMBEDDING_API_KEY
    echo   - POSTGRES_PASSWORD
    echo   - JWT_SECRET
    echo.
    exit /b 1
)

REM Check Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker not found!
    echo Please install Docker Desktop: https://docs.docker.com/desktop/install/windows-install/
    exit /b 1
)

docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ❌ docker-compose not found!
    exit /b 1
)

echo ✅ Environment check passed
echo.

REM Create logs directory
if not exist "logs" mkdir logs

REM Start infrastructure services
echo 🚀 Starting infrastructure services...
docker-compose up -d postgres redis prometheus grafana

echo ⏳ Waiting for PostgreSQL to be ready...
timeout /t 5 /nobreak >nul

REM Initialize database
echo 📊 Initializing database...
docker-compose exec -T postgres psql -U postgres -d context_compression < init-db.sql

echo ✅ Database initialized
echo.

REM Start Python recall service
echo 🐍 Starting Python recall service...
cd context-matcher-test
if not exist "venv" (
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -q -r requirements.txt
start /B python src\api_server_remote.py > ..\logs\recall-service.log 2>&1
cd ..

echo ✅ Recall service started
echo.

REM Start Go proxy service
echo 🔵 Starting Go proxy service...
cd go-proxy-service
start /B go run cmd\proxy\main.go > ..\logs\proxy-service.log 2>&1
cd ..

echo ✅ Proxy service started
echo.

REM Start admin dashboard
echo ⚛️  Starting admin dashboard...
cd admin-dashboard
call npm install
start /B npm run dev > ..\logs\dashboard.log 2>&1
cd ..

echo ✅ Dashboard started
echo.

REM Wait for services
echo ⏳ Waiting for services to be ready...
timeout /t 10 /nobreak >nul

echo.
echo ================================
echo 🎉 All services started!
echo ================================
echo.
echo 📍 Service URLs:
echo   • Admin Dashboard:  http://localhost:3000
echo   • Proxy API:        http://localhost:8080
echo   • Recall API:       http://localhost:8001
echo   • Prometheus:       http://localhost:9090
echo   • Grafana:          http://localhost:3001
echo.
echo 🔑 Test Service Key: sk-test-demo-key-12345678
echo.
echo 📖 Test in PowerShell:
echo   Invoke-RestMethod -Method POST -Uri "http://localhost:8080/api/v1/recall" `
echo     -Headers @{"Authorization"="Bearer sk-test-demo-key-12345678"} `
echo     -ContentType "application/json" `
echo     -Body '{"query":"test","history":["msg1","msg2"]}'
echo.
echo 🛑 To stop services:
echo   Run: stop-services.bat
echo   Or: docker-compose down
echo.
echo 📊 View logs in: logs\
echo.

pause
