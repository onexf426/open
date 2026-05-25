"""Remote file operations via SSH for multi-host license management."""

import os
import subprocess
import tempfile


def _get_host_ssh_cmd(host):
    """Build SSH command prefix from host config."""
    port = host.get('port', 22)
    user = host.get('username', 'root')
    hostname = host['hostname']
    base = ['-o', 'ConnectTimeout=10', '-o', 'StrictHostKeyChecking=no',
            '-p', str(port), f'{user}@{hostname}']
    if host.get('auth_type') == 'password':
        password = host.get('auth_value', '')
        return ['sshpass', '-p', password, 'ssh'] + base
    else:
        return ['ssh'] + base


def remote_read_file(host, path):
    """Read file content, works locally if host is None, via SSH if host is set."""
    if host is None:
        try:
            with open(path, 'r') as f:
                return f.read(), None
        except FileNotFoundError:
            return None, '文件不存在'
        except PermissionError:
            return None, '无权限读取'
        except Exception as e:
            return None, str(e)

    cmd = _get_host_ssh_cmd(host) + ['cat', path]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if r.returncode == 0:
            return r.stdout, None
        return None, r.stderr.strip() or 'SSH 读取失败'
    except subprocess.TimeoutExpired:
        return None, 'SSH 连接超时'
    except Exception as e:
        return None, str(e)


def remote_write_file(host, path, content):
    """Write content to file. If host is set, uses SSH."""
    if host is None:
        try:
            bak = path + '.bak'
            if os.path.exists(path):
                with open(path, 'r') as f:
                    old = f.read()
                with open(bak, 'w') as f:
                    f.write(old)
            with open(path, 'w') as f:
                f.write(content)
            return True, f'写入成功 (备份: {bak})' if os.path.exists(bak) else '写入成功'
        except Exception as e:
            return False, str(e)

    # Remote: create temp file locally, scp to remote
    with tempfile.NamedTemporaryFile(mode='w', suffix='.tmp', delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Backup via SSH first
        port = host.get('port', 22)
        user = host.get('username', 'root')
        hostname = host['hostname']
        remote_bak = path + '.bak'
        password_prefix = (['sshpass', '-p', host.get('auth_value', '')]
                          if host.get('auth_type') == 'password' else [])
        scp_prefix = (['sshpass', '-p', host.get('auth_value', '')]
                     if host.get('auth_type') == 'password' else [])

        # Make backup
        bak_cmd = password_prefix + ['ssh', '-o', 'StrictHostKeyChecking=no',
                    '-p', str(port), f'{user}@{hostname}',
                    f'cp {path} {remote_bak} 2>/dev/null; true']
        subprocess.run(bak_cmd, capture_output=True, timeout=10)

        # SCP the file
        scp_cmd = scp_prefix + ['scp', '-o', 'StrictHostKeyChecking=no',
                   '-P', str(port), tmp_path,
                   f'{user}@{hostname}:{path}']
        r = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=15)

        if r.returncode == 0:
            return True, f'远程写入成功 (备份: {remote_bak})'
        return False, r.stderr.strip() or 'SCP 失败'
    except Exception as e:
        return False, str(e)
    finally:
        os.unlink(tmp_path)


def remote_file_exists(host, path):
    """Check if a file exists."""
    if host is None:
        return os.path.exists(path)

    cmd = _get_host_ssh_cmd(host) + ['test', '-f', path]
    r = subprocess.run(cmd, capture_output=True, timeout=10)
    return r.returncode == 0


def remote_read_lines(host, path, max_lines=None):
    """Read file lines, returns (lines_list, error)."""
    content, error = remote_read_file(host, path)
    if error:
        return None, error
    lines = content.split('\n')
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
    return lines, None
