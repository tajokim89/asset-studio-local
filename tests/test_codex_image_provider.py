import io
import json
from pathlib import Path
import tempfile
import time
import unittest
import subprocess
from unittest.mock import patch
from PIL import Image
from asset_studio.codex_image_provider import CodexImageProvider, ProviderFailure, RpcSession


class Process:
    def __init__(self, lines):
        self.stdin = io.StringIO()
        self.stdout = io.StringIO(''.join(json.dumps(line) + '\n' for line in lines))
        self.terminated = False
    def poll(self): return 0 if self.terminated else None
    def terminate(self): self.terminated = True
    def wait(self, timeout): return 0
    def kill(self): self.terminated = True


class TransportTests(unittest.TestCase):
    def test_rpc_framing_and_queued_notifications(self):
        process = Process([{'method': 'notification', 'params': {}}, {'id': 1, 'result': {'ok': True}}])
        rpc = RpcSession(['codex'], '.', popen=lambda *a, **kw: process)
        self.assertEqual(rpc.call('initialize', {'text': 'a\nb'}), {'ok': True})
        request = json.loads(process.stdin.getvalue())
        self.assertEqual(request['params']['text'], 'a\nb')
        self.assertEqual(rpc.event()['method'], 'notification')
        rpc.close()
        self.assertTrue(process.terminated)

    def test_approval_denied(self):
        process = Process([{'id': 8, 'method': 'item/commandExecution/requestApproval', 'params': {}}])
        rpc = RpcSession(['codex'], '.', popen=lambda *a, **kw: process)
        with self.assertRaises(ProviderFailure) as error: rpc.next()
        self.assertEqual(error.exception.code, 'unsupported')
        self.assertIn('error', json.loads(process.stdin.getvalue()))
        rpc.close()

    def test_timeout(self):
        rpc = RpcSession(['codex'], '.', popen=lambda *a, **kw: Process([]))
        rpc.deadline = time.monotonic() - 1
        with self.assertRaises(ProviderFailure) as error: rpc.next()
        self.assertEqual(error.exception.code, 'timeout')
        rpc.close()


class FakeRpc:
    def __init__(self, command, cwd, timeout):
        self.job = Path(cwd)
        self.calls = []
        self.closed = False
        self.image = self.job / 'native.png'
        Image.new('RGB', (8, 8), 'red').save(self.image)
        self.events = [
            {'method': 'item/completed', 'params': {'threadId': 't', 'turnId': 'u', 'item': {'type': 'imageGeneration', 'status': 'completed', 'savedPath': str(self.image)}}},
            {'method': 'turn/completed', 'params': {'threadId': 't', 'turn': {'id': 'u', 'status': 'completed'}}},
        ]
    def call(self, method, params):
        self.calls.append((method, params))
        return {'initialize': {}, 'config/read': {'config': {'mcp_servers': {'test': {}}}}, 'thread/start': {'thread': {'id': 't'}, 'model': 'configured-model'}, 'turn/start': {'turn': {'id': 'u'}}}[method]
    def send(self, message): pass
    def event(self): return self.events.pop(0)
    def close(self): self.closed = True


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.provider = CodexImageProvider(self.root, command='codex.exe', session_factory=self.factory)
        self.provider.health = lambda: {'available': True}
    def tearDown(self): self.temp.cleanup()
    def factory(self, *args):
        self.rpc = FakeRpc(*args)
        return self.rpc
    def test_generation_and_config(self):
        result = self.provider.generate('red orc')
        self.assertTrue(result['success'], result)
        self.assertTrue(Path(result['image']).is_file())
        settings = dict(self.rpc.calls)['thread/start']
        self.assertEqual(settings['sandbox'], 'read-only')
        self.assertFalse(settings['config']['mcp_servers.test.enabled'])
        self.assertFalse(settings['config']['features.shell_tool'])
        self.assertTrue(self.rpc.closed)
    def test_missing_auth(self):
        self.provider.health = lambda: {'available': False, 'reason': 'auth_required'}
        result = self.provider.generate('orc')
        self.assertEqual(result['error_type'], 'auth_required')
        self.assertFalse(hasattr(self, 'rpc'))
    def test_missing_saved_path(self):
        def factory(*args):
            rpc = self.factory(*args)
            rpc.events[0]['params']['item'].pop('savedPath')
            return rpc
        self.provider.session_factory = factory
        self.assertEqual(self.provider.generate('orc')['error_type'], 'empty_response')
    def test_blocks_unexpected_tool(self):
        def factory(*args):
            rpc = self.factory(*args)
            rpc.events[0]['params']['item']['type'] = 'commandExecution'
            return rpc
        self.provider.session_factory = factory
        self.assertEqual(self.provider.generate('orc')['error_type'], 'unsupported')
        self.assertTrue(self.rpc.closed)
    def test_rejects_outside_path(self):
        outside = self.root / 'outside.png'
        Image.new('RGB', (8, 8)).save(outside)
        job = self.root / 'job'
        job.mkdir()
        with self.assertRaises(ProviderFailure):
            self.provider._copy_result(str(outside), job, self.root / 'generated')
    def test_symlink_escape(self):
        outside = self.root / 'outside.png'
        Image.new('RGB', (8, 8)).save(outside)
        job = self.root / 'job'
        job.mkdir()
        try: (job / 'escape.png').symlink_to(outside)
        except OSError: self.skipTest('symlink privilege unavailable')
        with self.assertRaises(ProviderFailure):
            self.provider._copy_result(str(job / 'escape.png'), job, self.root / 'generated')
    def test_mask_unsupported(self):
        self.assertEqual(self.provider.generate('orc', mask_image_url='anything')['error_type'], 'unsupported')
    def test_reference_validation(self):
        self.assertEqual(self.provider.generate('orc', image_url='http://127.0.0.1/image')['error_type'], 'invalid_image_input')
        self.assertEqual(self.provider.generate('orc', image_url='data:image/png;base64,@@@')['error_type'], 'invalid_image_input')
    def test_reference_forwarding(self):
        self.assertTrue(self.provider.generate('orc', image_url='data:image/png;base64,YQ==')['success'])
        self.assertEqual(dict(self.rpc.calls)['turn/start']['input'][1]['type'], 'image')


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.provider = CodexImageProvider(Path.cwd(), command='codex.exe')
    def result(self, code=0, out='', err=''):
        return subprocess.CompletedProcess([], code, out, err)
    @patch('asset_studio.codex_image_provider.subprocess.run')
    def test_local_ready_is_not_claimed_as_generation_verified(self, run):
        run.side_effect = [self.result(err='Logged in using ChatGPT'), self.result(out='image_generation stable true\n')]
        state = self.provider.health()
        self.assertTrue(state['available'])
        self.assertEqual(state['reason'], 'local_ready_not_generation_verified')
        self.assertEqual(state['provider'], 'codex_oauth')
        self.assertEqual(run.call_args_list[0].args[0], ['codex.exe', 'login', 'status'])
    @patch('asset_studio.codex_image_provider.subprocess.run')
    def test_missing_auth_does_not_leak_command_output(self, run):
        run.return_value = self.result(1, err='private diagnostic token sentinel')
        state = self.provider.health()
        self.assertFalse(state['available'])
        self.assertEqual(state['reason'], 'auth_required')
        self.assertNotIn('sentinel', json.dumps(state))
        self.assertEqual(run.call_count, 1)
    @patch('asset_studio.codex_image_provider.subprocess.run')
    def test_api_key_login_is_not_chatgpt_oauth(self, run):
        run.return_value = self.result(err='Logged in using an API key')
        self.assertEqual(self.provider.health()['reason'], 'auth_required')
    @patch('asset_studio.codex_image_provider.subprocess.run')
    def test_disabled_image_feature(self, run):
        run.side_effect = [self.result(err='Logged in using ChatGPT'), self.result(out='image_generation stable false\n')]
        self.assertFalse(self.provider.health()['available'])
    @patch('asset_studio.codex_image_provider.subprocess.run')
    def test_login_timeout_is_safe(self, run):
        run.side_effect = subprocess.TimeoutExpired('codex', 10)
        self.assertFalse(self.provider.health()['available'])


class ServerRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server
        cls.server = server
    def test_loads_native_provider_without_hermes(self):
        with patch.object(self.server, 'CodexImageProvider') as provider:
            instance = self.server.load_provider()
        provider.assert_called_once_with(output_dir=self.server.GENERATED / 'codex-images')
        self.assertIs(instance, provider.return_value)
    def test_health_routes_native_safe_metadata(self):
        with patch.object(self.server, 'load_provider') as load:
            load.return_value.health.return_value = {'available': False, 'reason': 'auth_required', 'provider': 'codex_oauth'}
            state = self.server.provider_health()
        self.assertEqual(state['integration_mode'], 'codex-native-chatgpt')
        self.assertFalse(state['available'])
        self.assertEqual(state['reason'], 'auth_required')
    def test_page_reference_generation_uses_native_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.png'
            Image.new('RGB', (8, 8), 'red').save(path)
            with patch.object(self.server, 'load_provider') as load:
                backend = load.return_value
                backend.capabilities.return_value = {'modalities': ['text', 'image'], 'max_reference_images': 5, 'supports_edit_mask': False}
                backend.generate.return_value = {'success': True, 'image': str(path), 'model': 'configured-model'}
                raw, metadata = self.server.generate_with_page_image_backend('make an orc', image_url='data:image/png;base64,YQ==')
            self.assertEqual(raw, path.read_bytes())
            self.assertEqual(metadata['provider'], 'codex-native')
            self.assertEqual(metadata['reference_roles'], ['direction_master'])
            backend.generate.assert_called_once()


if __name__ == '__main__': unittest.main()

