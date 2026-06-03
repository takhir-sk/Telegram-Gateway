@echo off
title Сборщик проекта для ИИ

echo Запуск процесса сборки...

:: Проверяем, установлен ли Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ОШИБКА] Python не найден! Убедитесь, что он установлен и добавлен в PATH.
    pause
    exit /b
)

:: Запускаем наш Python-скрипт
if exist collect.py (
    python collect.py
) else (
    echo [ОШИБКА] Файл collect.py не найден в этой папке.
    pause
    exit /b
)

echo.
echo Все готово! Теперь ты можешь скопировать project_summary.md.
pause