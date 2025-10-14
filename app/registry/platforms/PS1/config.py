# app/registry/platforms/duckstation/config.py
def get_config():
    return {
        "name": "DuckStation",
        "install_method": "appimage",
        "appimage_url": "https://github.com/stenzek/duckstation/releases/download/latest/DuckStation-x64.AppImage",
        "appimage_filename": "DuckStation-x64.AppImage",
        "supported_formats": [".bin", ".cue", ".chd", ".pbp"],
        "needs_extraction": False,
        "bios_required": True,
        "bios_files": [
            "scph5501.bin",
            "Sony PlayStation BIOS (E)(v2.0)(1995-05-10)[SCPH-1002].bin",
            "Sony PlayStation BIOS (E)(v2.2)(1995-12-04)[DTLH-3002].bin",
            "Sony PlayStation BIOS (E)(v3.0)(1997-01-06)[SCPH-5502 + SCPH-5552].bin",
            "Sony PlayStation BIOS (E)(v4.1)(1997-12-16)[SCPH-7502 + SCPH-9002].bin",
            "Sony PlayStation BIOS (J)(v1.1)(1995-01-22)[SCPH-3000].bin",
            "Sony PlayStation BIOS (J)(v2.2)(1995-12-04)[SCPH-5000].bin",
            "Sony PlayStation BIOS (J)(v2.2)(1995-12-04)[SCPH-5000][h].bin",
            "Sony PlayStation BIOS (J)(v4.0)(1997-08-18)[SCPH-7000].bin",
            "Sony PlayStation BIOS (J)[SCPH-1000].bin",
            "Sony PlayStation BIOS (U)(v3.0)(1996-11-18)[SCPH-7003].bin",
            "Sony PlayStation BIOS (U)(v4.1)(1997-12-16)[SCPH-7001 + SCPH-9001].bin"
        ],
        "platform_name": "Sony PlayStation",
        "emulator": "duckstation"
    }
