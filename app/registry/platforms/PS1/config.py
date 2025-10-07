def get_config():
    """Возвращает конфигурацию модуля PS1"""
    return {
        "name": "DuckStation",
        "install_method": "appimage",
        "appimage_url": "https://github.com/stenzek/duckstation/releases/download/latest/DuckStation-x64.AppImage",
        "appimage_filename": "DuckStation-x64.AppImage",
        "install_command": [
            "wget", "https://github.com/stenzek/duckstation/releases/download/latest/DuckStation-x64.AppImage",
            "-O", "DuckStation-x64.AppImage",
            "&&", "chmod", "+x", "DuckStation-x64.AppImage"
        ],
        "supported_formats": [".bin", ".cue", ".chd", ".pbp"],
        "needs_extraction": False,
        "bios_required": True,
        "bios_files": ["scph1001.bin", "scph5500.bin", "scph5501.bin", "scph5502.bin"],
        "platform_name": "Sony PlayStation",
        "emulator": "duckstation"
    }
