def get_config():
    """Возвращает конфигурацию модуля PS2"""
    return {
        "name": "PCSX2",
        "install_method": "appimage",
        "appimage_url": None,  # Будет определено динамически
        "appimage_filename": None,  # Будет определено динамически
        "supported_formats": [".iso", ".chd", ".mdf", ".mds"],
        "needs_extraction": False,
        "bios_required": True,
        "bios_files": ["ps2-0230a-20040620.bin", "ps2-0230e-20040620.bin", "ps2-0230j-20040620.bin"],
        "platform_name": "Sony PlayStation 2",
        "emulator": "pcsx2",
        "version": None,  # Будет определено динамически
        "auto_update": True,
        "include_prerelease": True
    }
