def get_config():
    """Возвращает конфигурацию модуля PS3"""
    return {
        "name": "RPCS3",
        "install_method": "appimage",
        "appimage_url": "https://github.com/RPCS3/rpcs3-binaries-linux/releases/download/build-9e49b9100fab7293c5f616f6aebc91799461c26c/rpcs3-v0.0.38-18185-9e49b910_linux64.AppImage",
        "appimage_filename": "rpcs3.AppImage",
        "install_command": [
            "wget", "https://github.com/RPCS3/rpcs3-binaries-linux/releases/download/build-9e49b9100fab7293c5f616f6aebc91799461c26c/rpcs3-v0.0.38-18185-9e49b910_linux64.AppImage",
            "-O", "rpcs3.AppImage",
            "&&", "chmod", "+x", "rpcs3.AppImage"
        ],
        "supported_formats": [".iso", ".pkg"],
        "needs_extraction": False,
        "bios_required": True,
        "bios_files": ["PS3UPDAT.PUP"],
        "platform_name": "Sony PlayStation 3",
        "emulator": "rpcs3",
        "version": "0.0.38"
    }
