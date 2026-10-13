#!/usr/bin/python3
"""Application uninstaller. No package operation runs without a reviewed plan."""
import os
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio, GLib

@dataclass
class App:
    name: str
    kind: str
    identifier: str
    desktop: str

PROTECTED = {'ubuntu-desktop', 'ubuntu-desktop-minimal', 'gnome-shell', 'gnome-session', 'gdm3', 'nautilus', 'systemd', 'apt', 'dpkg', 'sudo', 'polkitd', 'python3', 'python3-gi'}

def run(args):
    return subprocess.run(args, capture_output=True, text=True, env={**os.environ, 'LC_ALL': 'C'})

def apt_plan(package):
    if not re.fullmatch(r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?', package):
        raise ValueError('Nom de paquet invalide.')
    result = run(['/usr/bin/apt-get', '--simulate', 'remove', package])
    if result.returncode:
        raise ValueError(result.stderr or result.stdout)
    removed = re.findall(r'^Remv (\S+)', result.stdout, re.M)
    if not removed:
        raise ValueError('Ce paquet n’est plus installé.')
    if any(p.split(':')[0] in PROTECTED or p.startswith(('linux-image-', 'linux-modules-', 'linux-headers-')) for p in removed):
        raise ValueError('Cette suppression toucherait un composant du système ou du bureau. Elle est bloquée.')
    for p in removed:
        flags = run(['/usr/bin/dpkg-query', '-W', '-f=${Essential} ${Priority}', p]).stdout
        if flags.startswith('yes') or flags.endswith(('required', 'important')):
            raise ValueError('Suppression bloquée : composant système important (' + p + ').')
    return removed

def apps():
    result = []
    seen = set()
    for item in Gio.AppInfo.get_all():
        if not item.should_show() or not hasattr(item, 'get_filename'):
            continue
        filename = item.get_filename()
        if not filename:
            continue
        path = Path(filename)
        flatpak = item.get_string('X-Flatpak')
        if flatpak:
            kind = 'Flatpak utilisateur' if str(path).startswith(str(Path.home())) else 'Flatpak système'
            identifier = flatpak
        elif '/snapd/desktop/' in filename:
            kind, identifier = 'Snap', path.stem.split('_', 1)[0]
        elif str(path).startswith(str(Path.home() / '.local/share/applications') + '/'):
            kind, identifier = 'Lanceur local', filename
            executable = item.get_executable() or ''
            binary = Path(executable)
            if binary.is_absolute() and binary.suffix.lower() == '.appimage' and binary.is_file():
                if binary.resolve().is_relative_to(Path.home().resolve()):
                    kind, identifier = 'AppImage', str(binary)
        else:
            owner = run(['/usr/bin/dpkg-query', '-S', filename])
            if owner.returncode:
                continue
            kind, identifier = 'APT', owner.stdout.split(': ', 1)[0].split(', ')[0]
        key = (kind, identifier)
        if key not in seen:
            seen.add(key)
            result.append(App(item.get_display_name(), kind, identifier, filename))
    return sorted(result, key=lambda a: a.name.casefold())

class Uninstaller(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='io.github.ubuntu_desktop_toolkit.Uninstaller')
        self.connect('activate', self.activate_window)
        self.items = []
        self.busy = False

    def activate_window(self, *_):
        self.window = Gtk.ApplicationWindow(application=self, title='Désinstaller des applications')
        self.window.set_default_size(730, 650)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for side in ('top', 'bottom', 'start', 'end'):
            getattr(box, 'set_margin_' + side)(18)
        self.window.set_child(box)
        self.search = Gtk.SearchEntry(placeholder_text='Rechercher une application…')
        self.search.connect('search-changed', lambda *_: self.render())
        box.append(self.search)
        box.append(Gtk.Label(label='APT, Snap, Flatpak et lanceurs locaux.\nChaque suppression est confirmée. Les données personnelles sont conservées.', xalign=0, wrap=True))
        scroll = Gtk.ScrolledWindow(vexpand=True)
        self.list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        scroll.set_child(self.list)
        box.append(scroll)
        self.status = Gtk.Label(label='Chargement des applications…', xalign=0, wrap=True)
        box.append(self.status)
        refresh = Gtk.Button(label='Actualiser la liste')
        refresh.connect('clicked', lambda *_: self.load())
        box.append(refresh)
        self.window.present()
        self.load()

    def load(self):
        if self.busy:
            return
        self.busy = True
        self.status.set_text('Recherche des applications installées…')
        def worker():
            try:
                items = apps()
                GLib.idle_add(self.loaded, items, None)
            except Exception as e:
                GLib.idle_add(self.loaded, [], str(e))
        threading.Thread(target=worker, daemon=True).start()

    def loaded(self, items, error):
        self.items = items
        self.busy = False
        self.render()
        self.status.set_text(error or f'{len(items)} applications trouvées. Sélectionne celle à désinstaller.')

    def render(self):
        while child := self.list.get_first_child():
            self.list.remove(child)
        text = self.search.get_text().casefold()
        for app in self.items:
            if text not in (app.name + ' ' + app.identifier).casefold():
                continue
            row = Gtk.Box(spacing=12)
            row.set_margin_top(9); row.set_margin_bottom(9)
            row.append(Gtk.Label(label=app.name + '\n' + app.kind + ' · ' + app.identifier, xalign=0, hexpand=True, wrap=True))
            button = Gtk.Button(label='Retirer du menu' if app.kind == 'Lanceur local' else 'Désinstaller')
            button.set_sensitive(not self.busy)
            button.connect('clicked', lambda _, a=app: self.prepare(a))
            row.append(button)
            self.list.append(row)

    def prepare(self, app):
        if self.busy:
            return
        self.busy = True
        self.render()
        self.status.set_text('Vérification de la suppression…')
        def worker():
            try:
                plan = apt_plan(app.identifier) if app.kind == 'APT' else [app.identifier]
                GLib.idle_add(self.confirm, app, plan)
            except Exception as e:
                GLib.idle_add(self.done, str(e))
        threading.Thread(target=worker, daemon=True).start()

    def confirm(self, app, plan):
        detail = 'Paquets qui seront retirés :\n' + '\n'.join(plan)
        if app.kind == 'Lanceur local':
            detail = 'Seul le raccourci du menu sera placé dans la corbeille.\nLe programme, son fichier AppImage éventuel et ses données resteront sur le disque.'
        elif app.kind == 'AppImage':
            detail = 'Le fichier AppImage et son raccourci seront placés dans la corbeille :\n' + app.identifier + '\nLes préférences et données sont conservées.'
        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True, message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.OK_CANCEL, text='Retirer ' + app.name + ' ?')
        dialog.set_property('secondary-text', detail)
        def response(d, choice):
            d.destroy()
            if choice == Gtk.ResponseType.OK:
                threading.Thread(target=self.remove, args=(app, plan), daemon=True).start()
            else:
                self.done('Suppression annulée.')
        dialog.connect('response', response)
        dialog.present()

    def remove(self, app, plan):
        try:
            if app.kind == 'APT':
                if apt_plan(app.identifier) != plan:
                    raise ValueError('Le plan a changé. Actualise la liste et recommence.')
                # The root helper validates the same plan immediately before APT.
                command = ['pkexec', '/usr/bin/python3', str(Path(__file__).resolve()), '--apt-remove', app.identifier, *plan]
            elif app.kind == 'Snap':
                command = ['pkexec', '/usr/bin/snap', 'remove', app.identifier]
            elif app.kind.startswith('Flatpak'):
                command = ['/usr/bin/flatpak', 'uninstall', '--noninteractive', '--user' if app.kind.endswith('utilisateur') else '--system', app.identifier]
                if app.kind.endswith('système'):
                    command = ['pkexec', *command]
            else:
                path = Path(app.desktop)
                if path.parent != Path.home() / '.local/share/applications':
                    raise ValueError('Lanceur hors du dossier autorisé.')
                if app.kind == 'AppImage':
                    binary = Path(app.identifier)
                    if not binary.resolve().is_relative_to(Path.home().resolve()) or binary.suffix.lower() != '.appimage':
                        raise ValueError('Fichier AppImage hors du dossier personnel.')
                    command = ['/usr/bin/gio', 'trash', str(binary), str(path)]
                else:
                    command = ['/usr/bin/gio', 'trash', str(path)]
            result = run(command)
            message = 'Suppression terminée. Tu peux actualiser la liste.' if result.returncode == 0 else 'Suppression non effectuée ou incomplète :\n' + (result.stderr or result.stdout)[-2000:]
        except Exception as e:
            message = str(e)
        GLib.idle_add(self.done, message)

    def done(self, message):
        self.busy = False
        self.render()
        self.status.set_text(message)

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == '--apt-remove':
        package, expected = sys.argv[2], sys.argv[3:]
        if os.geteuid() != 0 or apt_plan(package) != expected:
            raise SystemExit('Plan de suppression non valide.')
        raise SystemExit(subprocess.run(['/usr/bin/apt-get', '-y', 'remove', *expected], env={**os.environ, 'LC_ALL': 'C'}).returncode)
    Uninstaller().run()
