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
    echo         IMPORTANT: Check "Add Python to PATH" during installation!
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

REM Step 5: Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip --quiet 2>nul

REM Step 6: Install PyTorch with CUDA (or CPU fallback)
echo.
echo Detecting GPU for PyTorch installation...
nvidia-smi >nul 2>&1
if !errorlevel! equ 0 (
    echo [OK] NVIDIA GPU detected — installing PyTorch with CUDA support
    echo     This downloads ~2.5 GB, please be patient...
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121 --quiet
    if !errorlevel! neq 0 (
        echo [WARNING] CUDA PyTorch install failed, trying CPU version...
        pip install torch torchaudio --quiet
    )
) else (
    echo [INFO] No NVIDIA GPU detected — installing CPU-only PyTorch
    echo        Mario will work but voice will be slower.
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu --quiet
    if !errorlevel! neq 0 (
        pip install torch torchaudio --quiet
    )
)
echo [OK] PyTorch installed

REM Step 7: Install server dependencies
echo.
echo Installing server dependencies...
pip install -r server\requirements.txt --quiet
if !errorlevel! neq 0 (
    echo [WARNING] Some server dependencies failed. Retrying with verbose output...
    pip install -r server\requirements.txt
)
echo [OK] Server dependencies installed

REM Step 8: Install client dependencies
echo Installing client dependencies...
pip install -r client\requirements.txt --quiet
if !errorlevel! neq 0 (
    echo [WARNING] Some client dependencies failed. Mario display may not work.
)
echo [OK] Client dependencies installed

REM Step 8.5: Install character creator dependencies
echo Installing character creator dependencies...
pip install -r character_creator\requirements.txt --quiet
echo [OK] Character creator dependencies installed

REM Step 9: Detect hardware tier
echo.
echo Detecting hardware...
python -c "import sys; sys.path.insert(0, '.'); from server.hardware import detect_hardware; hw=detect_hardware(); v,r,c=hw['gpu_vram_gb'],hw['ram_gb'],hw['cpu_cores']; print('ultra' if v>=20 and r>=128 and c>=32 else 'high' if v>=10 and r>=32 and c>=8 else 'medium' if v>=6 and r>=16 else 'low')" > _setup_tier.tmp 2>nul
set /p TIER=<_setup_tier.tmp
del _setup_tier.tmp 2>nul
if "!TIER!"=="" set TIER=low
echo [OK] Hardware tier: !TIER!

REM Step 10: Download models (if needed)
if not exist "mario_models_new\GPT_SoVITS_Mario\Mario-e20.ckpt" (
    if not exist "server\data\rvc_model\SuperMario-TITAN_e500_s13000.pth" (
        echo Downloading voice models from GitHub Release (~930 MB^)...
        curl.exe -L -o models-v2.1.zip https://github.com/VillaKeth/Mario-Bathroom-AI/releases/download/v2.1/models-v2.1.zip
        if !errorlevel! neq 0 (
            echo [WARNING] Model download failed. Mario will use Edge TTS fallback voice.
            echo           Manual download: https://github.com/VillaKeth/Mario-Bathroom-AI/releases
        ) else (
            echo Extracting models...
            powershell -Command "Expand-Archive -Force 'models-v2.1.zip' '.'"
            del models-v2.1.zip 2>nul
            echo [OK] Models extracted
        )
    ) else (
        echo [OK] Voice models already present
    )
) else (
    echo [OK] Voice models already present
)

REM Step 11: GPT-SoVITS setup (if venv not exists)
if not exist "gpt_sovits_env\Scripts\python.exe" (
    echo.
    echo Setting up GPT-SoVITS voice cloning (this takes 5-15 minutes^)...
    if not exist "gpt_sovits_repo" (
        echo Cloning GPT-SoVITS repository...
        git clone https://github.com/RVC-Boss/GPT-SoVITS.git gpt_sovits_repo
        if !errorlevel! neq 0 (
            echo [WARNING] Failed to clone GPT-SoVITS. Mario will use Edge TTS fallback voice.
            goto :skip_sovits
        )
    )
    pushd gpt_sovits_repo
    powershell -ExecutionPolicy Bypass -File install.ps1 -Device CU128 -Source HF
    popd
    echo [OK] GPT-SoVITS installed
) else (
    echo [OK] GPT-SoVITS already set up
)
:skip_sovits

REM Step 12: Pull Ollama models based on tier
echo.
echo Pulling Ollama models for !TIER! tier...
call :pull_model "llama3" "llama3" "~4.7 GB"
echo [OK] llama3 ready

if "!TIER!"=="ultra" (
    call :pull_model "llama3.1:70b" "llama3.1:70b-q4_k_m" "~40 GB, this will take a while"
    echo [OK] llama3.1:70b ready
    call :pull_model "mixtral:8x7b" "mixtral:8x7b" "~26 GB"
    echo [OK] mixtral:8x7b ready
)

REM Step 13: Fish Speech (ULTRA only)
if "!TIER!"=="ultra" (
    echo Installing Fish Speech TTS...
    pip install "fish-speech>=2.2.0" --quiet 2>nul
    if !errorlevel! neq 0 (
        echo [WARNING] Fish Speech install failed. This is optional - GPT-SoVITS will be primary.
    ) else (
        echo [OK] Fish Speech installed
    )
)

REM Step 14: Generate config.json
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

REM Step 15: Run verification
echo.
echo Running setup verification...
echo.
python scripts\verify_setup.py

echo.
echo  ========================================
echo   Setup Complete!
echo.
echo   TO START MARIO:
echo     1. Run: start_server.bat
echo     2. Run: start_client.bat (in a second terminal)
echo.
echo   That's it! No other setup needed.
echo  ========================================
echo.

REM Check if any characters exist (besides _shared and test_bot)
set HAS_CHARS=0
for /d %%d in (characters\*) do (
    if /I not "%%~nxd"=="_shared" if /I not "%%~nxd"=="test_bot" set HAS_CHARS=1
)
if !HAS_CHARS!==0 (
    echo.
    echo  No characters found! Launching Character Creator Wizard...
    echo  Create your first character in the browser.
    echo.
    start http://localhost:8766
    python -m character_creator.server
)
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
