#!/usr/bin/python3
"""Install the full toolkit per-user; preserve existing files and settings."""
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
DATA = Path.home() / '.local/share/ubuntu-desktop-toolkit'
SCHEMA = 'io.github.yannmasoch.nautilus-my-computer'
MEDIA = 'org.gnome.settings-daemon.plugins.media-keys'


def quoted(path):
    return '"' + str(path).replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$').replace('`', '\\`').replace('%', '%%') + '"'


def digest(content):
    return hashlib.sha256(content).hexdigest()


def install(dependencies=False):
    if os.geteuid() == 0:
        raise SystemExit('Lance cet installateur avec ton compte utilisateur, sans sudo.')
    if dependencies:
        subprocess.run(['pkexec', '/usr/bin/apt-get', 'install', '-y', 'python3-gi', 'gir1.2-gtk-4.0', 'gir1.2-adw-1', 'python3-nautilus', 'gettext', 'zenity', 'wl-clipboard', 'xclip', 'gnome-system-monitor', 'lxsession-edit', 'rar', 'xdg-utils'], check=True)
    required = ['gsettings', 'glib-compile-schemas', 'msgfmt', 'xdg-user-dir']
    missing = [name for name in required if not shutil.which(name)]
    if missing:
        raise SystemExit('Dépendances manquantes : ' + ', '.join(missing) + '. Relance avec --dependencies.')
    DATA.mkdir(parents=True, exist_ok=True)
    manifest = DATA / 'manifest.json'
    previous = json.loads(manifest.read_text()) if manifest.exists() else {}
    if isinstance(previous, list):
        previous = {'files': previous, 'settings': []}
    records = {item['path']: item for item in previous.get('files', [])}
    settings = {(item['schema'], item['key']): item for item in previous.get('settings', [])}

    def save_manifest():
        manifest.write_text(json.dumps({'files': list(records.values()), 'settings': list(settings.values())}, indent=2))

    def write(path, content, executable=False, only_new=False):
        if only_new and path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise ValueError('Fichier lié : installation refusée pour ' + str(path))
        if path.exists() and path.read_bytes() == content and str(path) not in records:
            return  # Already present before the toolkit: do not claim or delete it.
        if path.exists() and path.read_bytes() != content and str(path) not in records:
            backup = path.with_name(path.name + '.before-toolkit')
            if backup.exists():
                raise ValueError('Une sauvegarde existe déjà : ' + str(backup))
            shutil.copy2(path, backup)
        path.write_bytes(content)
        if executable:
            path.chmod(0o755)
        records[str(path)] = {'path': str(path), 'sha256': digest(content)}
        save_manifest()

    def configure(schema, key, value):
        old = subprocess.check_output(['gsettings', 'get', schema, key], text=True).strip()
        if old == value:
            return
        marker = (schema, key)
        if marker not in settings:
            settings[marker] = {'schema': schema, 'key': key, 'before': old, 'installed': value}
        else:
            settings[marker]['installed'] = value
        save_manifest()
        subprocess.run(['gsettings', 'set', schema, key, value], check=True)

    applications = Path.home() / '.local/share/applications'
    launchers = []
    for filename, name, icon in [('cleaner.py', 'Nettoyer les caches', 'aptdaemon-cleanup'), ('uninstaller.py', 'Désinstaller des applications', 'system-software-install')]:
        script = DATA / filename
        write(script, (ROOT / 'apps' / filename).read_bytes(), True)
        entry = f'[Desktop Entry]\nType=Application\nName={name}\nExec=/usr/bin/python3 {quoted(script)}\nIcon={icon}\nTerminal=false\nCategories=System;Utility;\n'
        launcher = applications / ('ubuntu-toolkit-' + filename.removesuffix('.py') + '.desktop')
        write(launcher, entry.encode())
        launchers.append((name, entry))
    startup = '[Desktop Entry]\nType=Application\nName=Applications au démarrage\nComment=Choisir les applications lancées à la connexion\nExec=lxsession-edit\nIcon=preferences-system\nTerminal=false\nCategories=Settings;\n'
    write(applications / 'ubuntu-toolkit-startup.desktop', startup.encode())
    scripts = Path.home() / '.local/share/nautilus/scripts'
    for source in (ROOT / 'nautilus-scripts').iterdir():
        if source.is_file():
            write(scripts / source.name, source.read_bytes(), True)

    # Respect localized XDG directory names. Never use the home directory as a template directory.
    templates = Path(subprocess.check_output(['xdg-user-dir', 'TEMPLATES'], text=True).strip())
    if templates != Path.home():
        for name, text in [('Document texte.txt', ''), ('Notes.md', '# Notes\n\n'), ('Script Python.py', '#!/usr/bin/env python3\n\n'), ('Script Bash.sh', '#!/usr/bin/env bash\n\n')]:
            write(templates / name, text.encode(), only_new=True)
    else:
        print('Le dossier Modèles est désactivé : aucun modèle créé.')
    desktop = Path(subprocess.check_output(['xdg-user-dir', 'DESKTOP'], text=True).strip())
    if desktop != Path.home():
        for name, entry in launchers:
            path = desktop / (name + '.desktop')
            write(path, entry.encode(), True)
            subprocess.run(['gio', 'set', str(path), 'metadata::trusted', 'true'], check=False, capture_output=True)

    # The bundled Ce PC implementation uses icon-view without changing folder defaults.
    vendor = ROOT / 'vendor/ce-pc'
    extensions = Path.home() / '.local/share/nautilus-python/extensions'
    for source in vendor.rglob('*'):
        relative = source.relative_to(vendor)
        if source.is_file() and (relative.parts[0] == 'nautilus_my_computer' or str(relative) == 'nautilus-my-computer.py'):
            if '__pycache__' not in relative.parts and source.suffix != '.pyc':
                write(extensions / relative, source.read_bytes())
    schema_dir = Path.home() / '.local/share/glib-2.0/schemas'
    write(schema_dir / (SCHEMA + '.gschema.xml'), (vendor / (SCHEMA + '.gschema.xml')).read_bytes())
    subprocess.run(['glib-compile-schemas', str(schema_dir)], check=True)
    for po in (vendor / 'po').glob('*.po'):
        with tempfile.TemporaryDirectory() as temporary:
            mo = Path(temporary) / 'translation.mo'
            subprocess.run(['msgfmt', str(po), '-o', str(mo)], check=True)
            write(Path.home() / '.local/share/locale' / po.stem / 'LC_MESSAGES/nautilus-my-computer.mo', mo.read_bytes())
    configure(SCHEMA, 'color-mode', "'flat'")
    configure(SCHEMA, 'custom-color', "'#0078D4'")
    configure(SCHEMA, 'show-system-partitions', 'false')
    configure(SCHEMA, 'start-on-disks', 'true')

    bindings = ast.literal_eval(subprocess.check_output(['gsettings', 'get', MEDIA, 'custom-keybindings'], text=True).strip().removeprefix('@as '))
    existing_monitor = False
    for path in bindings:
        custom = MEDIA + '.custom-keybinding:' + path
        command = subprocess.check_output(['gsettings', 'get', custom, 'command'], text=True).strip()
        binding = subprocess.check_output(['gsettings', 'get', custom, 'binding'], text=True).strip()
        if command == "'gnome-system-monitor'" and binding == "'<Control><Shift>Escape'":
            existing_monitor = True
    if not existing_monitor:
        path = '/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/ubuntu-toolkit-monitor/'
        custom = MEDIA + '.custom-keybinding:' + path
        for key, value in [('name', "'Moniteur système'"), ('command', "'gnome-system-monitor'"), ('binding', "'<Control><Shift>Escape'")]:
            configure(custom, key, value)
        if path not in bindings:
            configure(MEDIA, 'custom-keybindings', repr(bindings + [path]))
    if shutil.which('update-desktop-database'):
        subprocess.run(['update-desktop-database', str(applications)], check=False)
    save_manifest()
    print('Tout le toolkit est installé. Ferme les fenêtres de Fichiers puis reconnecte ta session pour charger Ce PC.')
    print('Ctrl + Maj + Échap : Moniteur système. F2 : renommage multiple natif.')
    print('Menu : Nettoyer les caches, Désinstaller des applications, Applications au démarrage.')


def uninstall():
    manifest = DATA / 'manifest.json'
    if not manifest.exists():
        return
    stored = json.loads(manifest.read_text())
    if isinstance(stored, list):
        stored = {'files': stored, 'settings': []}
    # Restore only settings that still have our installed value, before removing schemas.
    for entry in stored.get('settings', []):
        current = subprocess.check_output(['gsettings', 'get', entry['schema'], entry['key']], text=True).strip()
        if current == entry['installed']:
            subprocess.run(['gsettings', 'set', entry['schema'], entry['key'], entry['before']], check=True)
        elif entry['schema'] == MEDIA and entry['key'] == 'custom-keybindings':
            paths = ast.literal_eval(current.removeprefix('@as '))
            original = ast.literal_eval(entry['before'].removeprefix('@as '))
            added = set(ast.literal_eval(entry['installed'])) - set(original)
            subprocess.run(['gsettings', 'set', MEDIA, 'custom-keybindings', repr([p for p in paths if p not in added])], check=True)
    for entry in stored['files']:
        path = Path(entry['path'])
        if path.exists() and not path.is_symlink() and digest(path.read_bytes()) == entry['sha256']:
            path.unlink()
            backup = path.with_name(path.name + '.before-toolkit')
            if backup.exists():
                backup.replace(path)
    schema_dir = Path.home() / '.local/share/glib-2.0/schemas'
    if schema_dir.exists():
        subprocess.run(['glib-compile-schemas', str(schema_dir)], check=True)
    manifest.unlink()
    print('Toolkit retiré. Fichiers modifiés conservés ; anciennes versions et réglages non modifiés restaurés. Reconnecte ta session.')


if __name__ == '__main__':
    if '--uninstall' in sys.argv:
        uninstall()
    else:
        install('--dependencies' in sys.argv)
