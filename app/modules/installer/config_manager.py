#!/usr/bin/env python3
import shutil
from pathlib import Path
from datetime import datetime


class ConfigManager:
    def __init__(self, project_root: Path, logs_callback=None, test_mode=False):
        self.project_root = project_root
        self.logs_callback = logs_callback or (lambda msg: print(msg))
        self.test_mode = test_mode
        self._cancelled = False

    def _log(self, message: str):
        ts = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        line = f"{ts} [ConfigManager] {message}"
        self.logs_callback(line)

    def apply_config(self, game_id: str, platform: str):
        if self._cancelled:
            return False
            
        platform_dir = self.project_root / 'app' / 'emulators' / platform
        game_cfg = platform_dir / 'games' / f"{game_id}.json"
        default_cfg = platform_dir / 'preset_default.json'
        target_dir = self.project_root / 'users' / 'configs' / platform
        target_file = target_dir / f"{game_id}.json"

        if self._cancelled:
            return False

        if game_cfg.exists():
            self._log(f"📄 Найден игровой конфиг: {game_cfg}")
            if not self.test_mode:
                target_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy(game_cfg, target_file)
                self._log(f"✅ Конфиг скопирован в {target_file}")
            else:
                self._log("[TEST MODE] Симуляция копирования игрового конфига")
            return True

        if self._cancelled:
            return False

        if default_cfg.exists():
            self._log(f"📄 Использую дефолтный конфиг: {default_cfg}")
            if not self.test_mode:
                target_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy(default_cfg, target_file)
                self._log(f"✅ Дефолтный конфиг скопирован в {target_file}")
            else:
                self._log("[TEST MODE] Симуляция копирования дефолтного конфига")
            return True

        self._log(f"⚠️ Не найден ни игровой, ни дефолтный конфиг для {platform}")
        return False

    def cancel(self):
        self._cancelled = True
