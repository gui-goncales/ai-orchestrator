import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from backend.directory_picker import choose_directory


class DirectoryPickerTests(unittest.TestCase):
    def test_returns_selected_directory_from_native_dialog(self):
        with tempfile.TemporaryDirectory() as folder, patch('backend.directory_picker.sys.platform','darwin'), \
             patch('backend.directory_picker.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=folder+'\n',stderr='')) as run:
            self.assertEqual(choose_directory(),{'cancelled':False,'path':str(Path(folder).resolve())})
            args=run.call_args.args[0]
            self.assertEqual(args[0],'/usr/bin/osascript')
            self.assertIn('choose folder',args[-1])
            self.assertNotIn('shell',run.call_args.kwargs)

    def test_cancel_is_not_an_error_and_releases_picker(self):
        with patch('backend.directory_picker.sys.platform','darwin'), patch('backend.directory_picker.subprocess.run',return_value=SimpleNamespace(returncode=1,stdout='',stderr='User canceled. (-128)')):
            self.assertEqual(choose_directory(),{'cancelled':True})
            self.assertEqual(choose_directory(),{'cancelled':True})

    def test_timeout_releases_picker(self):
        with patch('backend.directory_picker.sys.platform','darwin'), patch('backend.directory_picker.subprocess.run',side_effect=subprocess.TimeoutExpired('picker',120)):
            for _ in range(2):
                with self.assertRaisesRegex(ValueError,'expirou'):choose_directory()

    def test_invalid_result_and_platform_are_explicit(self):
        with patch('backend.directory_picker.sys.platform','darwin'), patch('backend.directory_picker.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='',stderr='')):
            with self.assertRaises(ValueError):choose_directory()
        with patch('backend.directory_picker.sys.platform','linux'):
            with self.assertRaises(ValueError):choose_directory()
