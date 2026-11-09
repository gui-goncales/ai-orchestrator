"""Valida o upload HTTP e a criação de mensagem com anexo em banco isolado."""
import http.client
import json
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ChatAttachmentHTTPTests(unittest.TestCase):
    def test_upload_and_send_message(self):
        with tempfile.TemporaryDirectory(prefix='orchestrator-attachment-http-') as temp:
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            db_path = Path(temp) / 'test.sqlite3'
            process = subprocess.Popen(
                [sys.executable, '-m', 'backend.server', '--port', str(port), '--data', str(db_path)],
                cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
            try:
                origin = 'http://' + '127.0.0.1:' + str(port)
                for attempt in range(60):
                    if process.poll() is not None:
                        self.fail('Servidor encerrou: ' + process.stderr.read().decode(errors='replace')[-2000:])
                    try:
                        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=1)
                        conn.request('GET', '/api/health')
                        response = conn.getresponse()
                        response.read()
                        conn.close()
                        if response.status == 200:
                            break
                    except (OSError, TimeoutError):
                        time.sleep(0.1)
                else:
                    self.fail('Servidor não iniciou')

                boundary = 'orchestrator-test-boundary'
                payload = b'Conteudo do arquivo enviado pelo chat'
                crlf = bytes((13, 10))
                body = (b'--' + boundary.encode() + crlf
                    + b'Content-Disposition: form-data; name="file"; filename="exemplo.txt"' + crlf
                    + b'Content-Type: text/plain' + crlf + crlf
                    + payload + crlf + b'--' + boundary.encode() + b'--' + crlf)
                conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
                conn.request('POST', '/api/attachments', body, {
                    'Origin': origin,
                    'Content-Type': 'multipart/form-data; boundary=' + boundary,
                    })
                response = conn.getresponse()
                uploaded = json.loads(response.read())
                conn.close()
                self.assertEqual(response.status, 201, uploaded)
                self.assertTrue(uploaded.get('id'))

                message = {
                    'objective': 'Leia o arquivo anexado',
                    'project_id': 'local',
                    'provider': 'auto',
                    'workflow': 'auto',
                    'attachment_ids': [uploaded['id']],
                }
                conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
                conn.request('POST', '/api/tasks', json.dumps(message).encode(), {
                    'Origin': origin,
                    'Content-Type': 'application/json',
                    'Idempotency-Key': 'attachment-http-integration',
                    })
                response = conn.getresponse()
                created = json.loads(response.read())
                conn.close()
                self.assertEqual(response.status, 201, created)
                self.assertTrue(created.get('id'))

                with sqlite3.connect(str(db_path)) as db:
                    row = db.execute(
                        'SELECT task_id FROM chat_attachments WHERE id=?',
                        (uploaded['id'],),
                    ).fetchone()
                self.assertIsNotNone(row)
                self.assertEqual(row[0], created['id'])
            finally:
                process.terminate()
                try:
                    _, captured_stderr = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    _, captured_stderr = process.communicate(timeout=5)
                if captured_stderr:
                    print(captured_stderr.decode(errors="replace")[-5000:])


    if __name__ == '__main__':
        unittest.main()
