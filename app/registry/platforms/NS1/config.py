def get_config():
    """Возвращает конфигурацию модуля Nintendo Switch"""
    return {
        "name": "Nintendo Switch",
        "install_method": "flatpak",
        "flatpak_id": "org.yuzu_emu.yuzu",
        "install_command": ["flatpak", "install", "--user", "-y", "org.yuzu_emu.yuzu"],
        "supported_formats": [ ".nsp", ".xci", ".nca"],
        "needs_extraction": False,
        "bios_required": True,
        "bios_files": ["prod.keys", "title.keys"],
        "platform_name": "Nintendo Switch",
        "emulator": "Citron",  # эмулятор по умолчанию
        "description": "Гибридная консоль Nintendo с играми The Legend of Zelda, Mario Kart, Super Smash Bros",
        "available_emulators": ["citron", "eden", "yuzu", "ryujinx"],  # все доступные эмуляторы
        "recommended_emulator": "citron",
        "launcher_profiles": ["yuzu", "ryujinx"]
    }
