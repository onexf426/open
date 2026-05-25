import os
import stat
import datetime
import subprocess


def list_directory(path, host=None):
    """List directory contents. Supports remote hosts via SSH."""
    if host is None:
        return _list_local(path)
    return _list_remote(path, host)


def _list_local(path):
    """List directory on local filesystem."""
    if not os.path.exists(path):
        return [], f'Path not found: {path}'
    if not os.path.isdir(path):
        return [], f'Not a directory: {path}'

    try:
        names = sorted(os.listdir(path), key=lambda n: (not os.path.isdir(os.path.join(path, n)), n.lower()))
    except PermissionError:
        return [], f'Permission denied: {path}'
    except OSError as e:
        return [], str(e)

    entries = []
    for name in names:
        full = os.path.join(path, name)
        try:
            st = os.stat(full)
        except OSError:
            continue
        entries.append({
            'name': name,
            'is_dir': stat.S_ISDIR(st.st_mode),
            'size': st.st_size,
            'modified': datetime.datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M'),
        })
    return entries, None


def _list_remote(path, host):
    """List directory on remote host via SSH. Uses fast stat+ls approach."""
    port = host.get('port', 22)
    user = host.get('username', 'root')
    hostname = host['hostname']

    ssh_opts = [
        '-o', 'ConnectTimeout=3',
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'ControlMaster=auto',
        '-o', 'ControlPath=/tmp/ssh-%r@%h:%p',
        '-o', 'ControlPersist=30',
        '-p', str(port),
        f'{user}@{hostname}',
    ]

    if host.get('auth_type') == 'password':
        ssh_cmd = ['sshpass', '-p', host.get('auth_value', ''), 'ssh'] + ssh_opts
        scp_prefix = ['sshpass', '-p', host.get('auth_value', '')]
    else:
        ssh_cmd = ['ssh'] + ssh_opts
        scp_prefix = []

    # Use a compact shell command: stat to get name, type, size, mtime per file
    sh_cmd = (
        f"cd '{path}' 2>/dev/null && "
        "for f in * .[!.]*; do "
        "[ -e \"$f\" ] || continue; "
        "if [ -d \"$f\" ]; then t='d'; else t='f'; fi; "
        "s=$(stat -c%s \"$f\" 2>/dev/null || echo 0); "
        "m=$(stat -c%Y \"$f\" 2>/dev/null || echo 0); "
        "echo \"$f|$t|$s|$m\"; "
        "done | sort -t'|' -k2,2r -k1,1"
    )

    try:
        r = subprocess.run(
            ssh_cmd + [sh_cmd],
            capture_output=True, text=True, timeout=8
        )
        if r.returncode != 0:
            return [], f'SSH 错误: {r.stderr.strip() or r.stdout.strip()}'

        entries = []
        for line in r.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split('|')
            if len(parts) < 4:
                continue
            try:
                ts = datetime.datetime.fromtimestamp(int(parts[3]))
                modified = ts.strftime('%Y-%m-%d %H:%M')
            except (ValueError, OSError):
                modified = '?'
            entries.append({
                'name': parts[0],
                'is_dir': parts[1] == 'd',
                'size': int(parts[2]),
                'modified': modified,
            })
        return entries, None
    except subprocess.TimeoutExpired:
        return [], 'SSH 连接超时 (8s)'
    except Exception as e:
        return [], str(e)
