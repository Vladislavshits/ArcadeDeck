def get_latest_pcsx2_url():
    """Получает URL самой свежей версии PCSX2 AppImage (включая pre-release)"""
    try:
        response = requests.get("https://api.github.com/repos/PCSX2/pcsx2/releases")
        releases = response.json()

        # Сортируем релизы по дате создания (новые сначала)
        releases.sort(key=lambda x: x['created_at'], reverse=True)

        # Ищем первый подходящий релиз (включая pre-release)
        for release in releases:
            for asset in release['assets']:
                if 'linux-appimage-x64-Qt.AppImage' in asset['browser_download_url']:
                    print(f"Найдена версия: {release['tag_name']} (pre-release: {release.get('prerelease', False)})")
                    return asset['browser_download_url'], release['tag_name']

    except Exception as e:
        print(f"Ошибка получения версии PCSX2: {e}")

    # Fallback URL
    return "https://github.com/PCSX2/pcsx2/releases/latest/download/pcsx2-linux-appimage-x64-Qt.AppImage", "latest"

def get_config():
    """Возвращает конфигурацию модуля PS2"""
    latest_url, version_tag = get_latest_pcsx2_url()

    return {
        "name": "PCSX2",
        "install_method": "appimage",
        "appimage_url": latest_url,
        "appimage_filename": f"pcsx2-{version_tag}.AppImage",
        "install_command": [
            "wget", latest_url, "-O", f"pcsx2-{version_tag}.AppImage",
            "&&", "chmod", "+x", f"pcsx2-{version_tag}.AppImage"
        ],
        "supported_formats": [".iso", ".chd", ".mdf", ".mds"],
        "needs_extraction": False,
        "bios_required": True,
        "bios_files": ["ps2-0230a-20040620.bin", "ps2-0230e-20040620.bin", "ps2-0230j-20040620.bin"],
        "platform_name": "Sony PlayStation 2",
        "emulator": "pcsx2",
        "version": version_tag,
        "auto_update": True,
        "include_prerelease": True
    }
