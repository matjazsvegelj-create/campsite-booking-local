@echo off
cd /d "%~dp0"
if exist booking.db del /f /q booking.db
echo booking.db removed
