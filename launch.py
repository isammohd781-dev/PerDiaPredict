"""Launch three independent Streamlit applications from one project directory."""
import argparse
import hashlib
import os
from pathlib import Path
import socket
import subprocess
import sys
import webbrowser
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent
APPS = {'patient':8501, 'doctor':8502, 'admin':8503}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('portal', nargs='?', choices=[*APPS, 'all'], default='patient')
    args = parser.parse_args()
    os.chdir(ROOT)
    if not (3,11) <= sys.version_info[:2] <= (3,13):
        raise SystemExit('Use Python 3.11, 3.12 or 3.13.')
    selected = list(APPS) if args.portal == 'all' else [args.portal]
    for portal in selected:
        with socket.socket() as probe:
            probe.settimeout(.3)
            if probe.connect_ex(('127.0.0.1', APPS[portal])) == 0:
                raise SystemExit(f'Port {APPS[portal]} is already in use. Stop the previous server before starting {portal}.')
    env_dir = ROOT / '.venv'
    python = env_dir / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        subprocess.run([sys.executable, '-m', 'venv', str(env_dir)], check=True)
    check = subprocess.run([str(python), '-c', 'import sys; print(str(sys.version_info.major)+"."+str(sys.version_info.minor))'], capture_output=True, text=True, check=True)
    if check.stdout.strip() not in ('3.11','3.12','3.13'):
        raise SystemExit('The existing .venv uses an unsupported Python. Rename .venv to .venv_backup and start again. Keep your data files unchanged.')
    fingerprint = hashlib.sha256((ROOT / 'requirements.txt').read_bytes()).hexdigest()
    marker = env_dir / 'requirements.sha256'
    if not marker.exists() or marker.read_text() != fingerprint:
        subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt')], check=True)
        marker.write_text(fingerprint)
    processes = []
    try:
        for portal in selected:
            port = APPS[portal]
            processes.append(subprocess.Popen([str(python), '-m', 'streamlit', 'run', str(ROOT / (portal + '.py')), '--server.address=127.0.0.1', f'--server.port={port}', '--server.headless=true'], cwd=ROOT))
            print(f'{portal}: http://127.0.0.1:{port}/', flush=True)
        # With all three running, only open the patient page automatically.
        first_port = APPS[selected[0]]
        for _ in range(100):
            if processes[0].poll() is not None:
                raise SystemExit('The server stopped before it was ready. Check its error message above.')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{first_port}/_stcore/health', timeout=.5) as response:
                    if response.status == 200:
                        break
            except (OSError, urllib.error.URLError):
                time.sleep(.2)
        else:
            raise SystemExit('The server did not become ready. Check the terminal messages.')
        webbrowser.open(f'http://127.0.0.1:{first_port}/')
        while True:
            try:
                processes[0].wait(timeout=1)
                break
            except subprocess.TimeoutExpired:
                if any(p.poll() is not None for p in processes):
                    break
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == '__main__':
    main()
