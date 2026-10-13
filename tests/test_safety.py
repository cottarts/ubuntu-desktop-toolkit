import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def module(name):
    import sys
    spec = importlib.util.spec_from_file_location(name, ROOT / 'apps' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result

u = module('uninstaller')
c = module('cleaner')

class Safety(unittest.TestCase):
    def test_system_removal_blocked(self):
        with patch.object(u, 'run', return_value=subprocess.CompletedProcess([], 0, 'Remv gnome-shell [50]\n')):
            with self.assertRaises(ValueError):
                u.apt_plan('example')

    def test_required_package_blocked(self):
        with patch.object(u, 'run', side_effect=[subprocess.CompletedProcess([], 0, 'Remv package [1]\n'), subprocess.CompletedProcess([], 0, 'no important')]):
            with self.assertRaises(ValueError):
                u.apt_plan('package')

    def test_dependencies_in_plan(self):
        with patch.object(u, 'run', side_effect=[subprocess.CompletedProcess([], 0, 'Remv example [1]\nRemv plugin [1]\n'), subprocess.CompletedProcess([], 0, 'no optional'), subprocess.CompletedProcess([], 0, 'no optional')]):
            self.assertEqual(u.apt_plan('example'), ['example', 'plugin'])

    def test_package_name_rejected(self):
        with self.assertRaises(ValueError):
            u.apt_plan('--purge')

    def test_cache_cannot_follow_project_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / '.cache'; cache.mkdir()
            target = cache / 'blender'; target.mkdir()
            project = root / 'project'; project.mkdir()
            (project / 'scene').write_text('preserve')
            (target / 'link').symlink_to(project, target_is_directory=True)
            (target / 'temp').write_text('cache')
            with patch.object(c, 'CACHE', cache):
                c.clear_cache(target)
                with self.assertRaises(ValueError):
                    c.clear_cache(project)
            self.assertEqual((project / 'scene').read_text(), 'preserve')
            self.assertFalse(list(target.iterdir()))

    def test_ram_command_only_page_cache(self):
        with patch.object(c.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            c.clear_ram_cache()
            self.assertEqual(run.call_args_list[1].args[0], ['pkexec', '/usr/sbin/sysctl', '-w', 'vm.drop_caches=1'])

if __name__ == '__main__':
    unittest.main()
