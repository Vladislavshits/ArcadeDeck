# environment.py
import os
import sys
import subprocess
import traceback

def is_venv_active():
    """Проверяет, активировано ли виртуальное окружение"""
    return hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )

def activate_venv():
    """Активирует виртуальное окружение для текущего процесса"""
    try:
        # Определяем путь к venv
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))
        venv_path = os.path.join(base_dir, "venv")
        
        # Проверяем существование окружения
        if not os.path.exists(venv_path):
            raise RuntimeError(f"Virtual environment not found at {venv_path}")
        
        # Путь к активационному скрипту
        activate_script = os.path.join(venv_path, "bin", "activate")
        
        # Команда для активации
        activate_cmd = f"source {activate_script} && exec $SHELL -c"
        
        # Запускаем новый процесс с активированным окружением
        os.execl("/bin/bash", "/bin/bash", "-c", activate_cmd, *sys.argv)
        
    except Exception as e:
        print(f"Error activating virtual environment: {e}")
        traceback.print_exc()
        sys.exit(1)

def enforce_virtualenv():
    """Принудительно активирует окружение или завершает работу"""
    if not is_venv_active():
        print("Virtual environment not active. Attempting to activate...")
        try:
            activate_venv()
        except Exception as e:
            print(f"Failed to activate virtual environment: {e}")
            sys.exit(1)

def get_venv_python():
    """Возвращает путь к Python в виртуальном окружении"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))
    venv_path = os.path.join(base_dir, "venv")
    return os.path.join(venv_path, "bin", "python")

def run_in_venv(script_path, *args):
    """Запускает скрипт в виртуальном окружении"""
    venv_python = get_venv_python()
    if not os.path.exists(venv_python):
        venv_python = sys.executable
    
    command = [venv_python, script_path] + list(args)
    subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
