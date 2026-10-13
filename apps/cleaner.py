#!/usr/bin/python3
"""Nettoyeur graphique : liste explicite de caches, sans accès aux projets."""
import os
import shutil
import subprocess
import threading
import getpass
from pathlib import Path
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib

CACHE = Path.home() / '.cache'
GROUPS = [
    ('Miniatures des fichiers', ['thumbnails', 'gnome-desktop-thumbnailer'], []),
    ('Chrome : cache des fichiers web', ['google-chrome'], ['chrome', 'chromium']),
    ('Blender : cache utilisateur', ['blender'], ['blender']),
    ('Arnold / OptiX : cache de compilation GPU', ['/var/tmp/OptixCache_' + getpass.getuser(), '/tmp/OptixCache_' + getpass.getuser()], ['maya', 'mayabatch', 'Render', 'kick', 'houdini', 'husk', 'redshift', 'blender', 'Nuke', 'katana']),
    ('Redshift : textures, meshes et shaders en cache', [str(Path.home() / 'redshift/cache' / name) for name in ('Textures', 'Meshes', 'CompiledShaders')], ['maya', 'mayabatch', 'Render', 'redshift', 'houdini', 'husk', 'Cinema', 'katana']),
    ('Pilotes graphiques : shaders NVIDIA / Mesa', ['nvidia', 'mesa_shader_cache', 'mesa_shader_cache_db', 'radv_builtin_shaders', 'qtshadercache-x86_64-little_endian-lp64'], ['maya', 'blender', 'Render', 'resolve', 'houdini', 'Nuke', 'Unreal', 'wine', 'gamescope']),
    ('Installateurs Python téléchargés', ['pip', 'pipx'], ['pip', 'uv']),
    ('Installateurs Winetricks téléchargés', ['winetricks'], ['winetricks', 'wine']),
]

def size(path):
    if path.is_symlink() or not path.exists():
        return 0
    total = 0
    for root, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(root) / d).is_symlink()]
        for name in files:
            p = Path(root) / name
            try:
                if not p.is_symlink():
                    total += p.stat().st_blocks * 512
            except OSError:
                pass
    return total

def human(value):
    for unit in ('o', 'Ko', 'Mo', 'Go', 'To'):
        if value < 1024 or unit == 'To':
            return f'{value:.1f} {unit}'
        value /= 1024

def ram_cache_size():
    values = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        values[key] = int(value.strip().split()[0]) * 1024
    return max(0, values.get('Cached', 0) - values.get('Shmem', 0))

def clear_ram_cache():
    subprocess.run(['/usr/bin/sync'], check=True)
    return subprocess.run(['pkexec', '/usr/sbin/sysctl', '-w', 'vm.drop_caches=1'], capture_output=True, text=True)

def running():
    result = subprocess.run(['ps', '-eo', 'comm='], capture_output=True, text=True, check=True)
    return result.stdout.lower().splitlines()

def blocked(tokens, processes):
    return any((process == token.lower() if token in ('uv', 'pip') else token.lower() in process) for token in tokens for process in processes)

def clear_cache(path):
    # Seuls les chemins explicitement affichés dans les catégories sont autorisés.
    allowed = {CACHE / name for _, names, _ in GROUPS for name in names}
    if path not in allowed or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Chemin de cache non autorisé : ' + str(path))
    if not path.exists():
        return
    if path.stat().st_uid != os.getuid():
        raise ValueError('Ce cache appartient à un autre utilisateur.')
    for child in path.iterdir():
        if child.is_symlink() or child.is_file():
            child.unlink()
        elif child.is_dir():
            shutil.rmtree(child)

class Cleaner(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='io.github.ubuntu_desktop_toolkit.Cleaner')
        self.connect('activate', self.activate)

    def activate(self, app):
        self.window = Gtk.ApplicationWindow(application=self, title='Nettoyer les caches')
        self.window.set_default_size(620, 600)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for side in ('top', 'bottom', 'start', 'end'):
            getattr(box, 'set_margin_' + side)(20)
        self.window.set_child(box)
        heading = Gtk.Label(label='Choisis les caches à vider', xalign=0)
        heading.add_css_class('title-2')
        box.append(heading)
        box.append(Gtk.Label(label='Ferme les logiciels concernés avant le nettoyage.\nLes projets, préférences, mots de passe et sessions sont conservés.\nLes caches supprimés seront recréés au besoin.', wrap=True, xalign=0))
        self.rows = []
        for label, names, tokens in GROUPS:
            check = Gtk.CheckButton(label=label)
            box.append(check)
            self.rows.append((check, label, names, tokens))
        self.apt = Gtk.CheckButton(label='Ubuntu : paquets téléchargés (mot de passe administrateur)')
        box.append(self.apt)
        self.ram = Gtk.CheckButton(label='Cache RAM Linux (mot de passe administrateur)')
        box.append(self.ram)
        box.append(Gtk.Label(label='RAM : vide le cache des fichiers, pas la mémoire des applications.\nLinux le libère déjà au besoin ; le vider peut ralentir les accès suivants.', wrap=True, xalign=0))
        self.status = Gtk.Label(xalign=0, wrap=True)
        box.append(self.status)
        buttons = Gtk.Box(spacing=10)
        self.refresh = Gtk.Button(label='Actualiser')
        self.refresh.connect('clicked', lambda *_: self.scan())
        self.clean = Gtk.Button(label='Vider les caches sélectionnés')
        self.clean.add_css_class('destructive-action')
        self.clean.connect('clicked', self.confirm)
        buttons.append(self.refresh)
        buttons.append(self.clean)
        box.append(buttons)
        self.scan()
        self.window.present()

    def scan(self):
        processes = running()
        self.ram.set_label('Cache RAM Linux — environ ' + human(ram_cache_size()) + ' en cache (administrateur)')
        for check, label, names, tokens in self.rows:
            amount = sum(size(CACHE / name) for name in names)
            active = blocked(tokens, processes)
            check.set_label(f'{label} — {human(amount)}' + (' — logiciel ouvert' if active else ''))
            check.set_sensitive(not active and amount > 0)
            if active or not amount:
                check.set_active(False)
        self.status.set_text('Coche les catégories souhaitées, puis lance le nettoyage.\nLes catégories utilisées par un logiciel ouvert sont bloquées.')

    def confirm(self, *_):
        selected = [(label, names, tokens) for check, label, names, tokens in self.rows if check.get_active() and check.get_sensitive()]
        apt = self.apt.get_active()
        ram = self.ram.get_active()
        if not selected and not apt and not ram:
            self.status.set_text('Sélectionne au moins une catégorie.')
            return
        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True, message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.OK_CANCEL, text='Vider les caches sélectionnés ?')
        dialog.set_property('secondary-text', '\n'.join(label for label, _, _ in selected) + ('\nPaquets Ubuntu téléchargés' if apt else '') + ('\nCache RAM des fichiers : les prochains accès peuvent être plus lents.' if ram else ''))
        def response(d, result):
            d.destroy()
            if result == Gtk.ResponseType.OK:
                self.clean.set_sensitive(False)
                self.refresh.set_sensitive(False)
                self.status.set_text('Nettoyage en cours…')
                threading.Thread(target=self.perform, args=(selected, apt, ram), daemon=True).start()
        dialog.connect('response', response)
        dialog.present()

    def perform(self, selected, apt, ram):
        messages = []
        processes = running()
        for label, names, tokens in selected:
            if blocked(tokens, processes):
                messages.append(label + ' : ignoré, logiciel ouvert.')
                continue
            before = sum(size(CACHE / name) for name in names)
            try:
                for name in names:
                    clear_cache(CACHE / name)
                after = sum(size(CACHE / name) for name in names)
                messages.append(label + ' : ' + human(max(0, before - after)) + ' libérés.')
            except (OSError, ValueError) as exc:
                messages.append(label + ' : nettoyage incomplet — ' + str(exc))
        if apt:
            result = subprocess.run(['pkexec', '/usr/bin/apt-get', 'clean'], capture_output=True, text=True)
            messages.append('Cache Ubuntu nettoyé.' if result.returncode == 0 else 'Cache Ubuntu non nettoyé : authentification annulée ou erreur.')
        if ram:
            try:
                before = ram_cache_size()
                result = clear_ram_cache()
                after = ram_cache_size()
                messages.append('Cache RAM vidé : baisse observée de ' + human(max(0, before - after)) + '.' if result.returncode == 0 else 'Cache RAM non vidé : authentification annulée ou erreur.')
            except (OSError, subprocess.SubprocessError) as exc:
                messages.append('Cache RAM non vidé : ' + str(exc))
        GLib.idle_add(self.finish, messages)

    def finish(self, messages):
        self.scan()
        self.status.set_text('\n'.join(messages))
        self.clean.set_sensitive(True)
        self.refresh.set_sensitive(True)

if __name__ == '__main__':
    Cleaner().run()
