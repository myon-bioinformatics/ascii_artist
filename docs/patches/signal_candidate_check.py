"""Explicit rollout gate: ASCII_SIGNAL_LAUNCHER points at the candidate launcher.

Run with pytest explicitly; this pending-upstream gate is outside tests/.
"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import pytest


@pytest.mark.skipif(os.name != 'posix', reason='POSIX signal escalation')
@pytest.mark.parametrize('error_format', ['text', 'json'])
def test_sigint_then_sigterm(tmp_path, error_format):
    launcher = Path(os.environ['ASCII_SIGNAL_LAUNCHER']).resolve()
    child = tmp_path / 'child.py'
    ready, ack = tmp_path / 'ready', tmp_path / 'ack'
    child.write_text(
        'import signal, time\nfrom pathlib import Path\n'
        f'def interrupt(*args): Path({str(ack)!r}).touch()\n'
        'signal.signal(signal.SIGINT, interrupt)\n'
        f'Path({str(ready)!r}).touch()\n'
        'while True: time.sleep(0.01)\n'
    )
    entry = tmp_path / 'entry.cjs'
    entry.write_text(
        f'require({json.dumps(str(launcher))}).main({json.dumps(str(child))}, '
        f'{{python: {json.dumps(sys.executable)}, noSite: true}});\n'
    )
    env = dict(os.environ, PY_LAUNCH_ERROR_FORMAT=error_format, PYTHON=sys.executable)
    proc = subprocess.Popen([shutil.which('node'), str(entry)], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True)
    def wait_for(path):
        deadline = time.monotonic() + 10
        while not path.exists():
            assert proc.poll() is None, 'launcher exited before handshake'
            assert time.monotonic() < deadline, f'missing handshake: {path.name}'
            time.sleep(0.01)
    try:
        wait_for(ready)
        proc.send_signal(signal.SIGINT)
        wait_for(ack)
        proc.send_signal(signal.SIGTERM)
        out, err = proc.communicate(timeout=5)
        assert proc.returncode == 2
        assert out == ''
        if error_format == 'json':
            assert json.loads(err)['code'] == 'ESIGNAL'
        assert 'SIGTERM' in err
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate(timeout=5)
