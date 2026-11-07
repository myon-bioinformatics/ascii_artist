"""Keep stdlib flow checks runnable without the optional Node 26 adapter."""
import os
import re
import shutil
import subprocess


def supported_node():
    node = os.environ.get('NODE') or shutil.which('node')
    if not node:
        return None
    try:
        result = subprocess.run([node, '--version'], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.match(r'v(\d+)', result.stdout)
    return node if result.returncode == 0 and match and int(match[1]) >= 26 else None


NODE = supported_node()


# The documented Node entry: the shared launcher called directly (no per-tool wrapper).
NODE_ENTRY = [NODE, 'vendor/py_launch.cjs', '--env-var', 'ASCII_ARTIST_PYTHON', '--', 'ascii_artist.py'] if NODE else None


def node_command(command):
    return [[*NODE_ENTRY, command]] if NODE else []
