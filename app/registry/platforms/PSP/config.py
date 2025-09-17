def get_config():
    """Возвращает конфигурацию модуля PSP"""
    return {
        "name": "PPSSPP",
        "install_method": "flatpak",
        "flatpak_id": "org.ppsspp.PPSSPP",
        "install_command": ["flatpak", "install", "--user", "-y", "org.ppsspp.PPSSPP"],
        "supported_formats": [".iso", ".cso", ".chd", ".pbp", ".prx", ".elf"],
        "needs_extraction": True,
        "bios_required": False,
        "platform_name": "Sony PSP",
        "emulator": "ppsspp"
    }
