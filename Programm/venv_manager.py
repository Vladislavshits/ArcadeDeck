# venv_manager.py
import os
import sys
import subprocess
import traceback

# Глобальный флаг для отслеживания активации
_venv_activated = False

def is_venv_active() -> bool:
    """
    Проверяет, активировано ли виртуальное окружение.
    Возвращает True, если виртуальное окружение активно, иначе False.
    """
    return _venv_activated or hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )

def activate_venv_in_current_process() -> None:
    """
    Активирует виртуальное окружение в текущем процессе Python
    путем модификации sys.path и переменных окружения.
    """
    global _venv_activated
    try:
        # Определяем базовую директорию проекта
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        venv_path = os.path.join(base_dir, "venv")
        
        if not os.path.exists(venv_path):
            raise RuntimeError(f"Виртуальное окружение не найдено по адресу {venv_path}.")
        
        # Для Linux (Steam Deck)
        bin_path = os.path.join(venv_path, "bin")
        site_packages = os.path.join(venv_path, "lib", 
                                    f"python{sys.version_info.major}.{sys.version_info.minor}",
                                    "site-packages")
        
        # Добавляем пути в sys.path
        if site_packages not in sys.path:
            sys.path.insert(0, site_packages)
        
        # Обновляем PATH
        os.environ["PATH"] = bin_path + os.pathsep + os.environ.get("PATH", "")
        os.environ["VIRTUAL_ENV"] = venv_path
        
        # Устанавливаем флаг активации
        _venv_activated = True
        print(f"Виртуальное окружение активировано: {venv_path}")
        
    except Exception as e:
        print(f"Ошибка активации виртуального окружения: {e}")
        traceback.print_exc()
        sys.exit(1)

def enforce_virtualenv() -> None:
    """
    Принудительная проверка и активация виртуального окружения.
    Завершает выполнение программы, если виртуальное окружение не было успешно активировано.
    """
    if not is_venv_active():
        print("Виртуальное окружение неактивно. Попытка активации...")
        activate_venv_in_current_process()

def get_venv_python() -> str:
    """
    Возвращает полный путь к интерпретатору Python внутри виртуального окружения.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    venv_path = os.path.join(base_dir, "venv")
    return os.path.join(venv_path, "bin", "python")

def run_in_venv(script_path: str, *args) -> None:
    """
    Запускает указанный скрипт в виртуальном окружении.
    :param script_path: Путь к исполняемому скрипту.
    :param args: Аргументы командной строки, передаваемые в запускаемый скрипт.
    """
    venv_python = get_venv_python()
    
    if not os.path.exists(venv_python):
        venv_python = sys.executable
    
    command = [venv_python, script_path] + list(args)
    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
