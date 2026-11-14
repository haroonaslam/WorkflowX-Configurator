@echo off
setlocal
set "LIBRARY_PYTHON=%~dp0..\..\..\python_embeded\python.exe"
if exist "%LIBRARY_PYTHON%" goto launch
set "LIBRARY_PYTHON=%~dp0.venv\Scripts\python.exe"
if exist "%LIBRARY_PYTHON%" goto launch
set "LIBRARY_PYTHON=python"
:launch
"%LIBRARY_PYTHON%" "%~dp0image_prompt_library\launch.py"
if errorlevel 1 pause
