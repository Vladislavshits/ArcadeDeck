def get_config():
    """Возвращает конфигурацию модуля Nintendo DS"""
    return {
        "name": "MelonDS",
        "install_method": "appimage",
        "appimage_url": "https://github.com/melonDS-emu/melonDS/releases/download/1.1/melonDS-1.1-appimage-x86_64.zip",
        "appimage_filename": "melonDS-x86_64.AppImage",
        "supported_formats": [".nds", ".srl", ".7z", ".zip"],
        "needs_extraction": True,
        "bios_required": True,
        "bios_files": ["bios7.bin", "bios9.bin", "firmware.bin"],
        "platform_name": "Nintendo DS",
        "emulator": "melonds"
    }
