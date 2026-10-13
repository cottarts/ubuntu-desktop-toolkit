#!/usr/bin/python3
"""Install per-user launchers and scripts. Run as the desktop user, not root."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
DATA = Path.home() / '.local/share/ubuntu-desktop-toolkit'

def quoted(path):
    return '"' + str(path).replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$').replace('`', '\\`').replace('%', '%%') + '"'

def install(dependencies=False):
    if os.geteuid() == 0:
        raise SystemExit('Lance cet installateur avec ton compte utilisateur, sans sudo.')
    if dependencies:
        subprocess.run(['pkexec', '/usr/bin/apt-get', 'install', '-y', 'python3-gi', 'gir1.2-gtk-4.0', 'zenity', 'wl-clipboard', 'xclip', 'gnome-system-monitor', 'lxsession-edit'], check=True)
    DATA.mkdir(parents=True, exist_ok=True)
    records = []
    def write(path, content, executable=False):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != content:
            backup = path.with_name(path.name + '.before-toolkit')
            if not backup.exists():
                shutil.copy2(path, backup)
        path.write_bytes(content)
        if executable:
            path.chmod(0o755)
        records.append({'path': str(path), 'sha256': hashlib.sha256(content).hexdigest()})
    for filename, name, icon in [('cleaner.py', 'Nettoyer les caches', 'aptdaemon-cleanup'), ('uninstaller.py', 'Désinstaller des applications', 'system-software-install')]:
        script = DATA / filename
        write(script, (ROOT / 'apps' / filename).read_bytes(), True)
        entry = f'[Desktop Entry]\nType=Application\nName={name}\nExec=/usr/bin/python3 {quoted(script)}\nIcon={icon}\nTerminal=false\nCategories=System;Utility;\n'
        write(Path.home() / '.local/share/applications' / ('ubuntu-toolkit-' + filename.removesuffix('.py') + '.desktop'), entry.encode())
    scripts = Path.home() / '.local/share/nautilus/scripts'
    for source in (ROOT / 'nautilus-scripts').iterdir():
        if source.is_file():
            write(scripts / source.name, source.read_bytes(), True)
    subprocess.run(['update-desktop-database', str(Path.home() / '.local/share/applications')], check=False)
    (DATA / 'manifest.json').write_text(json.dumps(records, indent=2))
    print('Installé. Cherche « Nettoyer les caches » ou « Désinstaller des applications » dans le menu.')
    print('Les actions de Fichiers se trouvent dans clic droit → Scripts. Ferme et rouvre Fichiers au besoin.')

def uninstall():
    manifest = DATA / 'manifest.json'
    if not manifest.exists():
        return
    for entry in json.loads(manifest.read_text()):
        path = Path(entry['path'])
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']:
            path.unlink()
            backup = path.with_name(path.name + '.before-toolkit')
            if backup.exists():
                backup.replace(path)
    manifest.unlink()
    print('Les fichiers installés et non modifiés ont été retirés. Les anciennes versions sauvegardées ont été restaurées.')

if __name__ == '__main__':
    if '--uninstall' in sys.argv:
        uninstall()
    else:
        install('--dependencies' in sys.argv)
