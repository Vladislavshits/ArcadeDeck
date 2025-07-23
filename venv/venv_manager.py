# venv_manager.py
import os
import sys
import subprocess
import traceback


def is_venv_active() -> bool:
    """
    Проверяет, активировано ли виртуальное окружение.
    Возвращает True, если виртуальное окружение активно, иначе False.
    """
    return hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )


def activate_venv() -> None:
    """
    Активирует виртуальное окружение для текущего процесса.
    """
    try:
        # Определяем базовую директорию проекта относительно текущего местоположения скрипта
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        venv_path = os.path.join(base_dir, "venv")
        
        if not os.path.exists(venv_path):
            raise RuntimeError(f"Виртуальное окружение не найдено по адресу {venv_path}.")
        
        # Для Linux (Steam Deck)
        activate_script = os.path.join(venv_path, "bin", "activate")
        activate_cmd = f"source {activate_script}"
        os.system(activate_cmd)
        
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
        activate_venv()


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
        venv_python = sys.executable  # Использовать глобальную версию Python, если окружение не обнаружено
    
    command = [venv_python, script_path] + list(args)
    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
