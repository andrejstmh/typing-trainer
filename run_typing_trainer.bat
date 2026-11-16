@echo off
setlocal
if defined TYPING_TRAINER_PYTHON goto custom_python
where /q py
if errorlevel 1 goto path_python
py -3 -X utf8 "%~dp0main.py" %*
exit /b %errorlevel%

:path_python
python -X utf8 "%~dp0main.py" %*
exit /b %errorlevel%

:custom_python
"%TYPING_TRAINER_PYTHON%" -X utf8 "%~dp0main.py" %*
exit /b %errorlevel%
