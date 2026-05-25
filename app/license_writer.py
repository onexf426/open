import os
import shutil
from app.remote import remote_read_file, remote_write_file, remote_file_exists


def detect_daemon_conflicts(license_file_path, daemon_name, daemon_path, options_file, host=None):
    """Parse the DAEMON/VENDOR line in a license file and detect conflicts."""
    result = {
        'line_number': None, 'current_col3': None, 'current_col4': None,
        'col3_conflict': False, 'col4_conflict': False,
        'col3_empty': True, 'col4_empty': True,
        'daemon_line': None, 'keyword': 'DAEMON'
    }

    content, error = remote_read_file(host, license_file_path)
    if error:
        return result
    lines = content.split('\n')

    for i, line in enumerate(lines):
        stripped = line.strip()
        keyword = None
        if stripped.startswith('DAEMON'):
            keyword = 'DAEMON'
        elif stripped.startswith('VENDOR'):
            keyword = 'VENDOR'
        else:
            continue
        parts = stripped.split(None, 4)
        if len(parts) < 2:
            continue
        if parts[1] != daemon_name:
            continue

        result['line_number'] = i
        result['daemon_line'] = line
        result['keyword'] = keyword

        if len(parts) >= 3:
            result['current_col3'] = parts[2]
            result['col3_empty'] = False
            if daemon_path and parts[2] != daemon_path:
                result['col3_conflict'] = True

        if len(parts) >= 4:
            result['current_col4'] = parts[3]
            result['col4_empty'] = False
            if options_file and parts[3] != options_file:
                result['col4_conflict'] = True
        break
    return result


def force_write_daemon_line(license_file_path, daemon_name, daemon_path, options_file, host=None):
    """Force overwrite DAEMON/VENDOR line. Also updates SERVER hostname if host is provided."""
    content, error = remote_read_file(host, license_file_path)
    if error:
        return False, f'无法读取 license 文件: {error}'
    lines = content.split('\n')

    # 1. Update DAEMON/VENDOR line
    new_parts = ['DAEMON', daemon_name]
    if daemon_path:
        new_parts.append(daemon_path)
    if options_file:
        new_parts.append(options_file)
    new_daemon_line = ' '.join(new_parts)

    daemon_found = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        parts = stripped.split(None, 4)
        if len(parts) >= 2 and parts[0] in ('DAEMON', 'VENDOR') and parts[1] == daemon_name:
            lines[i] = new_daemon_line
            daemon_found = True
            break
    if not daemon_found:
        lines.append(new_daemon_line)

    # 2. Update SERVER line hostname if host is provided
    server_updated = False
    if host:
        target_hostname = host.get('hostname', '')
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('SERVER'):
                parts = stripped.split()
                if len(parts) >= 4 and target_hostname:
                    parts[1] = target_hostname
                    lines[i] = ' '.join(parts)
                    server_updated = True
                    break

    new_content = '\n'.join(lines)
    success, msg = remote_write_file(host, license_file_path, new_content)

    extra = ''
    if server_updated:
        extra = f' (SERVER hostname 已更新为 {host["hostname"]})'
    return success, msg + extra if success else msg


def detect_server_conflicts(license_file_path, host=None):
    """Parse SERVER line and detect hostname/port conflicts."""
    result = {'line_number': None, 'current_hostname': None, 'current_port': None, 'server_line': None}
    content, error = remote_read_file(host, license_file_path)
    if error:
        return result
    lines = content.split('\n')
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith('SERVER'):
            continue
        parts = stripped.split()
        result['line_number'] = i
        result['server_line'] = line
        if len(parts) >= 2:
            result['current_hostname'] = parts[1]
        if len(parts) >= 4:
            try:
                result['current_port'] = int(parts[3])
            except ValueError:
                pass
        break
    return result


def parse_license_port(license_file_path, host=None):
    """Extract the port from the SERVER line."""
    content, error = remote_read_file(host, license_file_path)
    if error:
        return None
    for line in content.split('\n'):
        stripped = line.strip()
        if not stripped.startswith('SERVER'):
            continue
        parts = stripped.split()
        if len(parts) >= 4:
            try:
                return int(parts[3])
            except ValueError:
                continue
    return None


def check_port_listening(hostname, port, timeout=3):
    """Check if a TCP port is listening."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        result = s.connect_ex((hostname, port))
        s.close()
        return result == 0
    except Exception:
        return False


def preview_license_file(license_file_path, max_lines=10, host=None):
    """Return the first N lines of a license file."""
    content, error = remote_read_file(host, license_file_path)
    if error:
        return None
    lines = [l for l in content.split('\n')][:max_lines]
    return '\n'.join(lines)
