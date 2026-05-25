import subprocess
import os
import re
import signal
import shutil


def _check_executable(filepath):
    """检查可执行文件是否可用，返回 (ok, error_message)。"""
    if not os.path.exists(filepath):
        return False, f'文件不存在: {filepath}'

    if not os.path.isfile(filepath):
        return False, f'路径不是普通文件: {filepath}'

    if not os.access(filepath, os.X_OK):
        return False, f'文件没有执行权限: {filepath}'

    # 尝试用 file 命令检查文件类型
    file_cmd = shutil.which('file')
    if file_cmd:
        try:
            result = subprocess.run([file_cmd, filepath], capture_output=True, text=True, timeout=5)
            file_info = result.stdout.strip()
        except Exception:
            file_info = '无法检测文件类型'
    else:
        file_info = None

    # 尝试获取 ELF 信息
    readelf = shutil.which('readelf')
    elf_class = None
    if readelf:
        try:
            result = subprocess.run([readelf, '-h', filepath], capture_output=True, text=True, timeout=5)
            for line in result.stdout.split('\n'):
                if 'Class' in line:
                    elf_class = line.strip()
                    break
        except Exception:
            pass

    # 尝试验证动态链接器是否存在 (仅对 ELF 文件)
    ldd = shutil.which('ldd')
    linker_issue = None
    if ldd and shutil.which('readelf'):
        try:
            result = subprocess.run([ldd, filepath], capture_output=True, text=True, timeout=10)
            if 'not found' in result.stdout or 'not found' in result.stderr:
                linker_issue = result.stdout + result.stderr
        except Exception:
            pass

    # 尝试直接执行 --version 来验证可运行性
    try:
        result = subprocess.run(
            [filepath, '--version'],
            capture_output=True, text=True, timeout=10,
            env={**os.environ, 'LD_LIBRARY_PATH': os.environ.get('LD_LIBRARY_PATH', '')}
        )
    except FileNotFoundError:
        # 这是关键：exec 失败，通常是找不到动态链接器
        detail_parts = [f'文件存在但无法执行: {filepath}']
        if elf_class:
            detail_parts.append(f'ELF: {elf_class}')
        if file_info:
            detail_parts.append(f'文件类型: {file_info}')
        if linker_issue:
            detail_parts.append(f'库/链接器缺失:\n{linker_issue}')
        detail_parts.append('可能原因: 缺少32位运行库(glibc.i686)或动态链接器不匹配')
        return False, '\n'.join(detail_parts)
    except PermissionError:
        return False, f'没有执行权限: {filepath}'
    except Exception as e:
        pass  # --version 可能不支持，忽略

    return True, None


def _get_lmgrd_from_config(config):
    lmgrd_path = config.get('lmgrd_path', '')
    if lmgrd_path and os.path.isfile(lmgrd_path):
        return lmgrd_path

    daemon_path = config.get('daemon_path', '')
    if daemon_path:
        daemon_dir = os.path.dirname(daemon_path)
        candidate = os.path.join(daemon_dir, 'lmgrd')
        if os.path.isfile(candidate):
            return candidate

    return 'lmgrd'


def start_license(config):
    lmgrd = config.get('lmgrd_path', 'lmgrd')
    license_file = config.get('license_file', '')
    log_path = config.get('log_path', '')

    if not license_file:
        return False, '未配置 License 文件', None

    if not os.path.isfile(license_file):
        return False, f'License 文件不存在: {license_file}', None

    # 预检查 lmgrd 是否可用
    ok, err = _check_executable(lmgrd)
    if not ok:
        return False, err, None

    cmd = [lmgrd, '-c', license_file]
    if log_path:
        cmd.extend(['-l', log_path])
    if config.get('extra_args'):
        cmd.extend(config['extra_args'].split())

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        pid = proc.pid
        try:
            proc.wait(timeout=2)
            return False, f'lmgrd 启动后立即退出 (退出码: {proc.returncode})', None
        except subprocess.TimeoutExpired:
            return True, f'启动成功 (PID: {pid})', pid
    except FileNotFoundError:
        return False, f'找不到 lmgrd: {lmgrd}', None
    except PermissionError:
        return False, f'lmgrd 没有执行权限: {lmgrd}', None
    except Exception as e:
        return False, str(e), None


def stop_license(config):
    lmgrd = config.get('lmgrd_path', 'lmgrd')
    license_file = config.get('license_file', '')
    daemon_path = config.get('daemon_path', '')

    if not license_file:
        return False, '未配置 License 文件'

    lmgrd_dir = os.path.dirname(lmgrd) if lmgrd and os.path.dirname(lmgrd) else ''
    lmdown = os.path.join(lmgrd_dir, 'lmdown') if lmgrd_dir else 'lmdown'

    cmd = [lmdown, '-c', license_file, '-q']
    if daemon_path:
        cmd.extend(['-vendor', daemon_path])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True, 'License 已停止'
        else:
            pid = config.get('pid')
            if pid:
                try:
                    os.kill(pid, signal.SIGTERM)
                    return True, f'License 已停止 (强制终止 PID {pid})'
                except ProcessLookupError:
                    return True, '进程已退出'
                except Exception as e:
                    return False, f'无法终止进程: {e}'
            return False, result.stderr.strip() or 'lmdown 执行失败'
    except FileNotFoundError:
        pid = config.get('pid')
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
                return True, f'License 已停止 (强制终止 PID {pid})'
            except ProcessLookupError:
                return True, '进程已退出'
            except Exception as e:
                return False, f'无法终止进程: {e}'
        return False, '找不到 lmdown 且没有 PID 可终止'
    except Exception as e:
        return False, str(e)


def reread_license(config):
    lmgrd = config.get('lmgrd_path', 'lmgrd')
    license_file = config.get('license_file', '')

    if not license_file:
        return False, '未配置 License 文件'

    lmgrd_dir = os.path.dirname(lmgrd) if lmgrd and os.path.dirname(lmgrd) else ''
    lmreread = os.path.join(lmgrd_dir, 'lmreread') if lmgrd_dir else 'lmreread'

    cmd = [lmreread, '-c', license_file]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True, 'License 重读成功'
        return False, result.stderr.strip() or 'lmreread 执行失败'
    except FileNotFoundError:
        return False, '找不到 lmreread'
    except Exception as e:
        return False, str(e)


def get_feature_usage(config):
    lmgrd = config.get('lmgrd_path', 'lmgrd')
    license_file = config.get('license_file', '')

    if not license_file:
        return [], '未配置 License 文件'

    lmgrd_dir = os.path.dirname(lmgrd) if lmgrd and os.path.dirname(lmgrd) else ''
    lmstat = os.path.join(lmgrd_dir, 'lmstat') if lmgrd_dir else 'lmstat'

    cmd = [lmstat, '-c', license_file, '-a']

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        output = result.stdout
        if not output:
            return [], result.stderr.strip() or 'lmstat 无输出'

        features = _parse_lmstat_output(output)
        features.sort(key=lambda x: x['used'], reverse=True)
        return features, None
    except FileNotFoundError:
        return [], '找不到 lmstat'
    except subprocess.TimeoutExpired:
        return [], 'lmstat 执行超时'
    except Exception as e:
        return [], str(e)


def get_feature_users(config, feature_name):
    lmgrd = config.get('lmgrd_path', 'lmgrd')
    license_file = config.get('license_file', '')

    lmgrd_dir = os.path.dirname(lmgrd) if lmgrd and os.path.dirname(lmgrd) else ''
    lmstat = os.path.join(lmgrd_dir, 'lmstat') if lmgrd_dir else 'lmstat'

    cmd = [lmstat, '-c', license_file, '-f', feature_name]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return _parse_lmstat_users(result.stdout, feature_name), None
    except Exception as e:
        return [], str(e)


def _parse_lmstat_output(output):
    features = []
    current_feature = None

    for line in output.split('\n'):
        m = re.match(r'Users of (\S+):.*Total of (\d+) license.*Total of (\d+) license.*in use', line, re.IGNORECASE)
        if m:
            if current_feature:
                features.append(current_feature)
            current_feature = {
                'feature': m.group(1),
                'total': int(m.group(2)),
                'used': int(m.group(3)),
                'vendor': '',
                'version': ''
            }

        if current_feature and 'vendor:' in line.lower():
            vm = re.search(r'vendor:\s*(\S+)', line, re.IGNORECASE)
            if vm:
                current_feature['vendor'] = vm.group(1)
        if current_feature and 'version:' in line.lower():
            vm = re.search(r'version:\s*(\S+)', line, re.IGNORECASE)
            if vm:
                current_feature['version'] = vm.group(1)

    if current_feature:
        features.append(current_feature)

    if not features:
        features = _parse_lmstat_simple(output)

    return features


def _parse_lmstat_simple(output):
    features = []
    for line in output.split('\n'):
        stripped = line.strip()
        if 'Users of' in stripped and 'licenses' in stripped.lower():
            m = re.search(r'Users of (\S+)', stripped)
            if m:
                feature_name = m.group(1)
                total_m = re.search(r'Total of (\d+) license', stripped, re.IGNORECASE)
                used_m = re.search(r'Total of (\d+) license.*in use', stripped, re.IGNORECASE)
                features.append({
                    'feature': feature_name,
                    'total': int(total_m.group(1)) if total_m else 0,
                    'used': int(used_m.group(1)) if used_m else 0,
                    'vendor': '',
                    'version': ''
                })
    return features


def _parse_lmstat_users(output, feature_name):
    users = []
    in_users = False

    for line in output.split('\n'):
        stripped = line.strip()
        if 'Users of' in stripped and feature_name in stripped:
            in_users = True
            continue
        if in_users:
            m = re.match(r'(\S+)\s+(\S+)\s+(\S+)\s+\(?(v?[\d.]+)?', stripped)
            if m:
                users.append({
                    'user': m.group(1),
                    'host': m.group(2),
                    'display': m.group(3),
                    'version': m.group(4) or ''
                })
            elif stripped == '' or 'licenses' in stripped.lower():
                in_users = False

    return users
