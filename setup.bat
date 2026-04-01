@echo off
setlocal enabledelayedexpansion
echo.
echo  ========================================
echo   Mario AI Party Bot - Setup Wizard
echo  ========================================
echo.

REM Step 1: Check Python 3.10+
python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>nul
if !errorlevel! neq 0 (
    echo [ERROR] Python 3.10+ required. Install from https://python.org
    pause
    exit /b 1
)
for /f "delims=" %%v in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"') do set PYVER=%%v
echo [OK] Python !PYVER! found

REM Step 2: Check Ollama installed
ollama --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Ollama not found. Install from https://ollama.ai
    pause
    exit /b 1
)
echo [OK] Ollama found

REM Step 3: Check Ollama service running
ollama list >nul 2>&1
if !errorlevel! neq 0 (
    echo [WARNING] Ollama service not running.
    echo          Open another terminal and run: ollama serve
    echo          Then press any key to continue...
    pause >nul
    ollama list >nul 2>&1
    if !errorlevel! neq 0 (
        echo [ERROR] Ollama service still not running. Please start it and re-run setup.
        pause
        exit /b 1
    )
)
echo [OK] Ollama service running

REM Step 4: Create Python venv (if not exists)
if not exist "venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    python -m venv venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
)
call venv\Scripts\activate.bat
echo [OK] Virtual environment active

REM Step 5: Install dependencies
echo Installing server dependencies...
pip install -r server\requirements.txt --quiet
echo Installing client dependencies...
pip install -r client\requirements.txt --quiet
echo [OK] Dependencies installed

REM Step 6: Detect hardware tier
REM NOTE: Uses temp file instead of for/f to avoid single-quote nesting issues in batch
echo Detecting hardware...
python -c "import sys; sys.path.insert(0, '.'); from server.hardware import detect_hardware; hw=detect_hardware(); v,r,c=hw['gpu_vram_gb'],hw['ram_gb'],hw['cpu_cores']; print('ultra' if v>=20 and r>=128 and c>=32 else 'high' if v>=10 and r>=32 and c>=8 else 'medium' if v>=6 and r>=16 else 'low')" > _setup_tier.tmp 2>nul
set /p TIER=<_setup_tier.tmp
del _setup_tier.tmp 2>nul
if "!TIER!"=="" set TIER=low
echo [OK] Hardware tier: !TIER!

REM Step 7: Download models (if needed)
REM Check multiple critical files to catch partial extractions
if not exist "mario_models_new\GPT_SoVITS_Mario\Mario-e20.ckpt" (
    if not exist "server\data\rvc_model\SuperMario-TITAN_e500_s13000.pth" (
        echo Downloading voice models from GitHub Release (~930 MB^)...
        curl.exe -L -o models-v2.1.zip https://github.com/VillaKeth/Mario-Bathroom-AI/releases/download/v2.1/models-v2.1.zip
        if !errorlevel! neq 0 (
            echo [ERROR] Download failed. Check your internet connection.
            echo         Manual download: https://github.com/VillaKeth/Mario-Bathroom-AI/releases
            pause
            exit /b 1
        )
        echo Extracting models...
        powershell -Command "Expand-Archive -Force 'models-v2.1.zip' '.'"
        del models-v2.1.zip 2>nul
        echo [OK] Models extracted
    ) else (
        echo [OK] Voice models already present
    )
) else (
    echo [OK] Voice models already present
)

REM Step 8: GPT-SoVITS setup (if venv not exists)
if not exist "gpt_sovits_env\Scripts\python.exe" (
    echo Setting up GPT-SoVITS voice cloning (this takes 5-15 minutes^)...
    if not exist "gpt_sovits_repo" (
        echo Cloning GPT-SoVITS repository...
        git clone https://github.com/RVC-Boss/GPT-SoVITS.git gpt_sovits_repo
        if !errorlevel! neq 0 (
            echo [ERROR] Failed to clone GPT-SoVITS. Check git and internet.
            pause
            exit /b 1
        )
    )
    pushd gpt_sovits_repo
    REM install.ps1 requires: -Device (CU126|CU128|CPU) -Source (HF|HF-Mirror|ModelScope)
    powershell -ExecutionPolicy Bypass -File install.ps1 -Device CU128 -Source HF
    popd
    echo [OK] GPT-SoVITS installed
) else (
    echo [OK] GPT-SoVITS already set up
)

REM Step 9: Pull Ollama models based on tier
echo Pulling Ollama models for !TIER! tier...
call :pull_model "llama3" "llama3" "~4.7 GB"
echo [OK] llama3 ready

if "!TIER!"=="ultra" (
    call :pull_model "llama3.1:70b" "llama3.1:70b-q4_k_m" "~40 GB, this will take a while"
    echo [OK] llama3.1:70b ready
    call :pull_model "mixtral:8x7b" "mixtral:8x7b" "~26 GB"
    echo [OK] mixtral:8x7b ready
)

REM Step 10: Fish Speech (ULTRA only)
if "!TIER!"=="ultra" (
    echo Installing Fish Speech TTS...
    pip install "fish-speech>=2.2.0" --quiet 2>nul
    if !errorlevel! neq 0 (
        echo [WARNING] Fish Speech install failed. This is optional - GPT-SoVITS will be primary.
    ) else (
        echo [OK] Fish Speech installed
    )
)

REM Step 11: Generate config.json
if not exist "config.json" (
    echo Creating config.json from template...
    copy config.example.json config.json >nul
    echo [OK] config.json created
    echo.
    echo  ** IMPORTANT: Edit config.json to customize: **
    echo     - birthday_person_name
    echo     - birthday_person_facts
    echo.
) else (
    echo [OK] config.json already exists
)

REM Step 12: Run verification
echo.
echo Running setup verification...
echo.
python scripts\verify_setup.py

echo.
echo  ========================================
echo   Setup Complete!
echo   Run: start_server.bat
echo   Then open: http://localhost:8765/chat
echo  ========================================
echo.
pause
exit /b 0

REM === Subroutines ===

:pull_model
REM %~1 = findstr pattern, %~2 = model to pull, %~3 = size description
ollama list 2>nul | findstr /C:"%~1" >nul
if !errorlevel! neq 0 (
    echo Pulling %~2 (%~3^)...
    ollama pull %~2
)
exit /b 0
