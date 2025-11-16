@echo off
REM Navigate to project directory
cd /d C:\Users\gaming pc\trading_bot

REM Activate virtual environment
call venv\Scripts\activate

REM Start bot.py in a new window
start "Trading Bot" cmd /k "call venv\Scripts\activate && python bot.py"

REM Start dashboard.py in a new window
start "Dashboard" cmd /k "call venv\Scripts\activate && streamlit run dashboard.py"

REM Start Gmail listener in a new window
start "Gmail Listener" cmd /k "call venv\Scripts\activate && python gmail_to_bot_pubsub.py"

REM Keep main window open
pause
