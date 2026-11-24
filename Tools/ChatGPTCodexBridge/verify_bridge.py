"""Mock all writes; additionally test real STDIO MCP handshake and read-only tools."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
import uuid
import queue
import threading

from mcp.types import LATEST_PROTOCOL_VERSION
from bridge import Bridge, FIXED_THREAD, ROOT


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.testdir=ROOT/'verification_runs'
        self.testdir.mkdir(exist_ok=True)
        self.calls=[]
        def runner(argv,**kwargs):
            self.calls.append((argv,kwargs))
            return subprocess.CompletedProcess(argv,0,'mock queue result','')
        self.bridge=Bridge(database=self.testdir/(uuid.uuid4().hex+'.sqlite3'),runner=runner)
    def test_preview_does_not_send(self):
        text,argv=self.bridge.prepare('- keep literal ` and $(anything)\n中文')
        self.assertFalse(self.calls)
        self.assertEqual(argv[argv.index('--thread')+1],FIXED_THREAD)
        self.assertIn('--message='+text,argv)
    def test_human_request_required(self):
        with self.assertRaises(ValueError):self.bridge.submit('test','request-00001',False)
        self.assertFalse(self.calls)
    def test_single_submission_and_dedup(self):
        a=self.bridge.submit('test','request-00002',True)
        b=self.bridge.submit('test','request-00002',True)
        self.assertEqual(a['state'],'queued')
        self.assertTrue(b['duplicate_suppressed'])
        self.assertEqual(len(self.calls),1)
        self.assertFalse(self.calls[0][1]['shell'])
        self.assertEqual(self.calls[0][1]['timeout'],35)
        self.assertFalse(a['execution_confirmed'])
        with self.assertRaises(ValueError):self.bridge.submit('changed','request-00002',True)
        self.assertEqual(len(self.calls),1)
    def test_timeout_is_not_retried(self):
        def timeout(*args,**kwargs):
            self.calls.append(True)
            raise subprocess.TimeoutExpired('mock',35)
        self.bridge.runner=timeout
        a=self.bridge.submit('test','request-00003',True)
        b=self.bridge.submit('test','request-00003',True)
        self.assertEqual(a['state'],'pending_or_delivery_unknown')
        self.assertTrue(b['duplicate_suppressed'])
        self.assertEqual(len(self.calls),1)
    def test_invalid_input_rejected(self):
        for text in ('  ','x\0z','x'*12001):
            with self.assertRaises(ValueError):self.bridge.submit(text,'request-00004',True)
        with self.assertRaises(ValueError):self.bridge.submit('test','bad',True)
        bad=dict(self.bridge.config,thread_id='00000000-0000-0000-0000-000000000000')
        with self.assertRaises(ValueError):Bridge(config=bad)
        self.assertFalse(self.calls)


def readonly_mcp():
    # Anonymous pipes avoid Windows restricted-executor access to asyncio's named pipes.
    flags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess,'CREATE_NO_WINDOW') else 0
    proc=subprocess.Popen([sys.executable,'-u',str(ROOT/'bridge.py')],cwd=str(ROOT),
                          stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                          text=True,encoding='utf-8',creationflags=flags)
    replies=queue.Queue()
    def reader():
        for line in proc.stdout:replies.put(json.loads(line))
    threading.Thread(target=reader,daemon=True).start()
    def send(method,params,number=None):
        message={'jsonrpc':'2.0','method':method,'params':params}
        if number is not None:message['id']=number
        proc.stdin.write(json.dumps(message)+'\n');proc.stdin.flush()
        if number is None:return
        while True:
            reply=replies.get(timeout=12)
            if reply.get('id')==number:
                assert 'error' not in reply,reply
                return reply['result']
    try:
        initialized=send('initialize',{'protocolVersion':LATEST_PROTOCOL_VERSION,'capabilities':{},
            'clientInfo':{'name':'bridge-readonly-verifier','version':'1.0'}},1)
        send('notifications/initialized',{})
        catalog=send('tools/list',{},2)
        tools={tool['name']:tool for tool in catalog['tools']}
        assert set(tools)=={'bridge_info','prepare_instruction','send_instruction'}
        assert tools['bridge_info']['annotations']['readOnlyHint']
        assert tools['send_instruction']['annotations']['readOnlyHint'] is False
        info=send('tools/call',{'name':'bridge_info','arguments':{}},3)
        preview=send('tools/call',{'name':'prepare_instruction','arguments':{'instruction':'只做连接预览，不发送。'}},4)
        denied=send('tools/call',{'name':'send_instruction','arguments':{'instruction':'must not send','request_id':'denied-00001'}},5)
        assert not info.get('isError') and not preview.get('isError') and denied['isError']
        return {'protocol':initialized['protocolVersion'],'tools':sorted(tools),
                'read_only_calls_passed':True,'unauthorized_send_rejected':True,'real_messages_sent':0}
    finally:
        proc.stdin.close()
        try:proc.wait(timeout=5)
        except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=5)


if __name__=='__main__':
    tests=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BridgeTests))
    if not tests.wasSuccessful():raise SystemExit(1)
    result=readonly_mcp()
    result.update(unit_tests=tests.testsRun,source_sha256=hashlib.sha256((ROOT/'bridge.py').read_bytes()).hexdigest(),
                  application_config_changed=False,live_target_delivery_verified=False)
    (ROOT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
