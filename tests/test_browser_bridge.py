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

    def test_timeout_before_dispatch_reports_not_submitted(self):
        bridge = BrowserBridge()
        result = bridge.request('a'*32, 'execute', 'fixture', threading.Event(), .01)
        self.assertEqual(result['reason'], 'local_dispatch_timeout')
        self.assertIs(result['submitted'], False)
        self.assertIsNone(bridge.next_job())

    def test_cancel_after_dispatch_preserves_uncertain_submission(self):
        bridge = BrowserBridge()
        cancel = threading.Event()
        results = []
        thread = threading.Thread(target=lambda: results.append(
            bridge.request('a'*32, 'execute', 'fixture', cancel, 2)))
        thread.start()
        job = None
        for _ in range(100):
            job = bridge.next_job()
            if job:
                break
            threading.Event().wait(.01)
        try:
            self.assertIsNotNone(job)
            cancel.set()
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(results[0]['reason'], 'capture_timeout')
            self.assertIsNone(results[0]['submitted'])
            self.assertFalse(bridge.complete(job['id'], {'status': 'completed', 'result': 'late'}))
        finally:
            cancel.set()
            thread.join(2)

    def test_rejects_invalid_response(self):
        with self.assertRaises(ValueError):
            BrowserBridge().complete('unknown', {'status':'completed','result':{'unexpected':True}})

    def test_long_timeout_and_binding_are_forwarded_without_three_minute_cap(self):
        bridge = BrowserBridge()
        cancel = threading.Event()
        thread = threading.Thread(target=lambda: bridge.request('a'*32, 'execute', 'fixture', cancel, 600,
                                                               {'url': 'fixture', 'count': 2}))
        thread.start()
        job = None
        for _ in range(100):
            job = bridge.next_job()
            if job: break
            threading.Event().wait(.01)
        try:
            self.assertGreater(job['timeout_ms'], 180000)
            self.assertEqual(job['context']['count'], 2)
            self.assertIsNone(bridge.next_job())
        finally:
            cancel.set()
            thread.join(2)
