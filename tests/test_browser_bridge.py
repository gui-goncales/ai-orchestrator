import threading
import unittest
from backend.browser_bridge import BrowserBridge


class BrowserBridgeTests(unittest.TestCase):
    def test_job_is_delivered_once_and_result_returns_to_waiting_adapter(self):
        bridge = BrowserBridge()
        result = []
        started = threading.Event()
        def request():
            started.set()
            result.append(bridge.request('a'*32, 'execute', 'fixture', threading.Event(), 2))
        thread = threading.Thread(target=request)
        thread.start()
        started.wait(1)
        job = None
        for _ in range(100):
            job = bridge.next_job()
            if job: break
            threading.Event().wait(.01)
        self.assertIsNotNone(job)
        self.assertIsNone(bridge.next_job())
        self.assertEqual(job['prompt'], 'fixture')
        self.assertTrue(bridge.complete(job['id'], {'status':'completed','result':'ok','usage':{}}))
        thread.join(3)
        self.assertEqual(result[0]['result'], 'ok')
        self.assertFalse(bridge.complete(job['id'], {'status':'completed','result':'duplicate'}))

    def test_cancel_cleans_up_pending_job(self):
        bridge = BrowserBridge()
        cancel = threading.Event(); cancel.set()
        result = bridge.request('a'*32, 'execute', '', cancel, 1)
        self.assertEqual(result['status'], 'cancelled')
        self.assertIsNone(bridge.next_job())

    def test_rejects_invalid_response(self):
        with self.assertRaises(ValueError):
            BrowserBridge().complete('unknown', {'status':'completed','result':{'unexpected':True}})
