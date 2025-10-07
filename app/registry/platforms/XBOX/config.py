def get_config():
    """Возвращает конфигурацию модуля Xbox"""
    return {
        "name": "Xemu",
        "install_method": "appimage",
        "appimage_url": "https://github.com/xemu-project/xemu/releases/download/v0.8.106/xemu-v0.8.106-x86_64.AppImage",
        "appimage_filename": "xemu.AppImage",
        "install_command": [
            "wget", "https://github.com/xemu-project/xemu/releases/download/v0.8.106/xemu-v0.8.106-x86_64.AppImage",
            "-O", "xemu.AppImage",
            "&&", "chmod", "+x", "xemu.AppImage"
        ],
        "supported_formats": [".iso", ".xiso", ".bin", ".xbe"],
        "needs_extraction": False,
        "bios_required": True,
        "bios_files": ["mcpx_1.0.bin", "complex_4627.bin", "xbox_hdd.qcow2"],
        "platform_name": "Microsoft Xbox",
        "emulator": "xemu",
        "description": "Эмулятор оригинальной Xbox с играми Halo, Ninja Gaiden, Fable",
        "version": "0.8.106",
        "release_date": "2025-09-29",
        "available_emulators": ["xemu"],
    }
