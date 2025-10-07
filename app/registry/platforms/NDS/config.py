def get_config():
    """Возвращает конфигурацию модуля Nintendo DS"""
    return {
        "name": "MelonDS",
        "install_method": "flatpak",
        "flatpak_id": "net.kuribo64.melonDS",
        "install_command": ["flatpak", "install", "--user", "-y", "net.kuribo64.melonDS"],
        "supported_formats": [".nds", ".srl", ".dsi", ".ids", ".7z", ".zip"],
        "needs_extraction": True,  # для архивов
        "bios_required": True,
        "bios_files": ["bios7.bin", "bios9.bin", "firmware.bin"],
        "platform_name": "Nintendo DS",
        "emulator": "melonds",
        "description": "Портативная консоль с двумя экранами и сенсорным управлением",
        "touch_controls": True,
        "dual_screen": True
    }
