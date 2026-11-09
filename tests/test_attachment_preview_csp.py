"""Regression checks for local attachment image previews."""
import unittest
from pathlib import Path


class AttachmentPreviewCSPTest(unittest.TestCase):
    def test_local_server_allows_blob_image_previews(self):
        server = (Path(__file__).resolve().parents[1] / 'backend' / 'server.py').read_text(encoding='utf-8')
        self.assertIn("img-src 'self' data: blob:;", server)

    def test_frontend_supports_image_preview_and_open(self):
        chat = (Path(__file__).resolve().parents[1] / 'frontend' / 'src' / 'components' / 'ChatView.tsx').read_text(encoding='utf-8')
        self.assertIn('URL.createObjectURL(file)', chat)
        self.assertIn('onOpen(url, file.name)', chat)
        self.assertIn('isPreviewableImage(file)', chat)


if __name__ == '__main__':
    unittest.main()
