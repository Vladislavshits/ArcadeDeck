def get_config():
    """Возвращает конфигурацию модуля Xbox 360"""
    return {
        "name": "Xenia",
        "install_method": "appimage",
        "appimage_url": "https://github.com/xenia-project/release-builds-windows/releases/download/v1.0.3204-master/xenia_master.zip",
        "appimage_filename": "xenia.AppImage",
        "install_command": [
            "wget", "https://github.com/xenia-project/release-builds-windows/releases/download/v1.0.3204-master/xenia_master.zip",
            "-O", "xenia.zip",
            "&&", "unzip", "xenia.zip",
            "&&", "chmod", "+x", "xenia"
        ],
        "supported_formats": [".iso", ".xex", ".god"],
        "needs_extraction": False,
        "bios_required": False,
        "bios_files": [],
        "platform_name": "Microsoft Xbox 360",
        "emulator": "xenia",
        "description": "Эмулятор Xbox 360 с играми Gears of War, Halo 3, Forza Horizon",
        "version": "1.0.3204",
        "release_date": "2024-11-15",
        "available_emulators": ["xenia"],
    }
