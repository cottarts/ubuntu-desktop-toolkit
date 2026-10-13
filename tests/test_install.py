import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('toolkit_install', ROOT / 'install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

class Install(unittest.TestCase):
    def test_full_install_uninstall_preserves_folders_and_templates(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            templates = home / 'Modèles'; templates.mkdir()
            custom = templates / 'Document texte.txt'; custom.write_text('mon modèle')
            settings = {(installer.MEDIA, 'custom-keybindings'): '@as []'}
            changed = []
            def output(args, **kw):
                if args[0] == 'xdg-user-dir':
                    return str(home / ('Modèles' if args[1] == 'TEMPLATES' else 'Bureau')) + '\n'
                return settings.get((args[2], args[3]), "''") + '\n'
            def run(args, **kw):
                if args[0] == 'gsettings':
                    settings[(args[2], args[3])] = args[4]
                    changed.append(args)
                if args[0] == 'msgfmt':
                    Path(args[args.index('-o') + 1]).write_bytes(b'test translation')
                return subprocess.CompletedProcess(args, 0, '', '')
            with patch.object(installer.Path, 'home', return_value=home), patch.object(installer, 'DATA', home / '.local/share/ubuntu-desktop-toolkit'), patch.object(installer.os, 'geteuid', return_value=1000), patch.object(installer.shutil, 'which', return_value='/usr/bin/example'), patch.object(installer.subprocess, 'check_output', side_effect=output), patch.object(installer.subprocess, 'run', side_effect=run):
                installer.install()
                self.assertTrue((home / '.local/share/nautilus-python/extensions/nautilus-my-computer.py').exists())
                self.assertTrue((home / '.local/share/nautilus/scripts/Créer une application…').exists())
                self.assertTrue((home / '.local/share/applications/ubuntu-toolkit-startup.desktop').exists())
                self.assertTrue((home / 'Bureau/Nettoyer les caches.desktop').exists())
                self.assertFalse(any('default-folder-viewer' in args for args in changed))
                self.assertEqual(custom.read_text(), 'mon modèle')
                installer.install()  # Reinstallation must preserve the original setting baseline.
                installer.uninstall()
                self.assertFalse((home / '.local/share/nautilus-python/extensions/nautilus-my-computer.py').exists())
                self.assertEqual(custom.read_text(), 'mon modèle')
                self.assertEqual(settings[(installer.MEDIA, 'custom-keybindings')], '@as []')

    def test_ce_pc_grid_independent_of_folder_setting(self):
        view = (ROOT / 'vendor/ce-pc/nautilus_my_computer/my_computer_view.py').read_text()
        self.assertIn('ext._view_mode = "icon-view"', view)
        self.assertNotIn('ext._view_mode = settings.get_string("default-folder-viewer")', view)
        self.assertIn('display_name="Ubuntu"', view)

if __name__ == '__main__':
    unittest.main()
