import os
import json
import time
import pty
import select
import threading
from flask import Flask, render_template, request, jsonify, redirect, url_for, Response
from flask_socketio import SocketIO, emit
from app.vendor import (
    init_db, list_vendors, get_vendor, save_vendor, update_vendor,
    delete_vendor, get_vendor_config_count
)
from app.config import (
    list_configs, get_config, save_config, delete_config,
    update_config_status, get_running_configs, build_lmgrd_command
)
from app.logger import add_log, get_logs, get_log_count, get_stats
from app.flexlm import start_license, stop_license, reread_license, get_feature_usage, get_feature_users
from app.filesystem import list_directory as list_directory_base
from app.license_parser import parse_license_expiry, get_expiry_alerts
from app.license_writer import detect_daemon_conflicts, detect_server_conflicts, force_write_daemon_line, parse_license_port, check_port_listening, preview_license_file
from app.host import list_hosts, get_host, save_host, delete_host as delete_host_record
from app.settings import get_setting, set_setting, get_all_settings
from app.backup import export_all, import_all
from app.notify import get_smtp_config, send_email

socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')

# Track active terminal sessions per sid
_terminal_sessions = {}

def create_app():
    app = Flask(__name__)
    app.secret_key = os.urandom(24)

    with app.app_context():
        init_db()

    # ===== Page Routes =====

    @app.route('/')
    def dashboard():
        configs = list_configs()
        stats = get_stats()
        recent_logs = get_logs(limit=10)
        warn_days = int(get_setting('expire_warn_days') or 30)
        expiry_alerts = get_expiry_alerts(configs, warn_days)
        hosts = list_hosts()

        # Group configs by host
        grouped = {}
        for c in configs:
            key = c.get('host_name') or '本机'
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(c)

        return render_template('dashboard.html', configs=configs, grouped=grouped,
                               stats=stats, recent_logs=recent_logs,
                               expiry_alerts=expiry_alerts, hosts=hosts)

    @app.route('/config/new')
    def config_new():
        vendors = list_vendors()
        hosts = list_hosts()
        exclude_dir = get_setting('global_exclude_dir')
        return render_template('config_edit.html', config=None, vendors=vendors, hosts=hosts,
                               exclude_dir=exclude_dir)

    @app.route('/config/<int:config_id>/edit')
    def config_edit(config_id):
        config = get_config(config_id)
        vendors = list_vendors()
        hosts = list_hosts()
        exclude_dir = get_setting('global_exclude_dir')
        return render_template('config_edit.html', config=config, vendors=vendors, hosts=hosts,
                               exclude_dir=exclude_dir)

    @app.route('/vendors')
    def vendor_page():
        vendors = list_vendors()
        hosts = list_hosts()
        for v in vendors:
            v['config_count'] = get_vendor_config_count(v['id'])
        # Group vendors by host
        vgrouped = {}
        for v in vendors:
            key = v.get('host_name') or '通用'
            if key not in vgrouped:
                vgrouped[key] = []
            vgrouped[key].append(v)
        return render_template('vendor_list.html', vendors=vendors, vgrouped=vgrouped, hosts=hosts)

    @app.route('/logs')
    def logs_page():
        return render_template('logs.html')

    @app.route('/monitor')
    def monitor():
        running = get_running_configs()
        return render_template('monitor.html', configs=running)

    @app.route('/monitor/<int:config_id>')
    def monitor_config(config_id):
        config = get_config(config_id)
        return render_template('monitor.html', configs=[config], active_config_id=config_id)

    @app.route('/terminal')
    def terminal():
        return render_template('terminal.html')

    @app.route('/config/<int:config_id>/log')
    def log_viewer(config_id):
        config = get_config(config_id)
        if not config:
            return redirect(url_for('dashboard'))
        return render_template('log_viewer.html', config=config)

    @app.route('/hosts')
    def host_page():
        hosts = list_hosts()
        return render_template('host_list.html', hosts=hosts)

    @app.route('/settings')
    def settings_page():
        settings = get_all_settings()
        return render_template('settings.html', settings=settings, vendors=list_vendors())

    @app.route('/usage')
    def trends_page():
        return render_template('trends.html')

    def _get_host_for_config(config):
        if config and config.get('host_id'):
            return get_host(config['host_id'])
        return None


# ===== API Routes =====

    @app.route('/api/config/save', methods=['POST'])
    def api_config_save():
        data = request.form.to_dict()
        if 'id' in data and data['id']:
            data['id'] = int(data['id'])
        else:
            data['id'] = None
        data['auto_start'] = 1 if data.get('auto_start') == 'on' else 0
        data['vendor_id'] = int(data['vendor_id']) if data.get('vendor_id') else None

        config_id = save_config(data)
        config = get_config(config_id)
        add_log(config['name'], 'SAVE', 'SUCCESS', '配置已保存')

        if data.get('auto_start'):
            _set_auto_start(config, True)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'config_id': config_id})
        return redirect(url_for('dashboard'))

    @app.route('/api/config/<int:config_id>/delete', methods=['POST'])
    def api_config_delete(config_id):
        config = get_config(config_id)
        if not config:
            return jsonify({'success': False, 'message': '配置不存在'}), 404
        name = config['name']
        delete_config(config_id)
        add_log(name, 'DELETE', 'SUCCESS', '配置已删除')
        return jsonify({'success': True, 'message': '配置已删除'})

    @app.route('/api/config/<int:config_id>/start', methods=['POST'])
    def api_config_start(config_id):
        config = get_config(config_id)
        if not config:
            return jsonify({'success': False, 'message': '配置不存在'}), 404

        success, message, pid = start_license(config)
        if success:
            update_config_status(config_id, 'running', pid)
        add_log(config['name'], 'START', 'SUCCESS' if success else 'FAILED', message)
        return jsonify({'success': success, 'message': message})

    @app.route('/api/config/<int:config_id>/stop', methods=['POST'])
    def api_config_stop(config_id):
        config = get_config(config_id)
        if not config:
            return jsonify({'success': False, 'message': '配置不存在'}), 404

        success, message = stop_license(config)
        if success:
            update_config_status(config_id, 'stopped', None)
        add_log(config['name'], 'STOP', 'SUCCESS' if success else 'FAILED', message)
        return jsonify({'success': success, 'message': message})

    @app.route('/api/config/<int:config_id>/reread', methods=['POST'])
    def api_config_reread(config_id):
        config = get_config(config_id)
        if not config:
            return jsonify({'success': False, 'message': '配置不存在'}), 404

        success, message = reread_license(config)
        add_log(config['name'], 'REREAD', 'SUCCESS' if success else 'FAILED', message)
        return jsonify({'success': success, 'message': message})

    @app.route('/api/config/<int:config_id>/enable', methods=['POST'])
    def api_config_enable(config_id):
        config = get_config(config_id)
        if not config:
            return jsonify({'success': False, 'message': '配置不存在'}), 404

        enable = request.form.get('enable', '1') == '1'
        _set_auto_start(config, enable)
        status_text = '已启用' if enable else '已禁用'
        add_log(config['name'], 'ENABLE', 'SUCCESS', f'开机自启{status_text}')
        return jsonify({'success': True, 'enabled': enable, 'message': f'开机自启{status_text}'})

    @app.route('/api/config/<int:config_id>/lmstat')
    def api_lmstat(config_id):
        config = get_config(config_id)
        if not config:
            return jsonify({'success': False, 'message': '配置不存在'}), 404

        features, error = get_feature_usage(config)
        if error:
            return jsonify({'success': False, 'message': error})
        return jsonify({'success': True, 'features': features})

    @app.route('/api/config/<int:config_id>/lmstat/users/<feature>')
    def api_lmstat_users(config_id, feature):
        config = get_config(config_id)
        if not config:
            return jsonify({'success': False, 'message': '配置不存在'}), 404

        users, error = get_feature_users(config, feature)
        if error:
            return jsonify({'success': False, 'message': error})
        return jsonify({'success': True, 'users': users})

    @app.route('/api/browse')
    def api_browse():
        path = request.args.get('path', '/')
        host_id = request.args.get('host_id', '')
        host = get_host(int(host_id)) if host_id else None
        entries, error = list_directory_base(path, host=host)
        if error:
            return jsonify({'success': False, 'message': error})
        parent = os.path.dirname(path) if path != '/' else '/'
        if path == '/':
            parent = '/'
        return jsonify({'success': True, 'path': path, 'parent': parent, 'entries': entries, 'host_id': host_id})

    @app.route('/api/logs')
    def api_logs():
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        logs = get_logs(limit=limit, offset=offset)
        total = get_log_count()
        return jsonify({'success': True, 'logs': logs, 'total': total})

    @app.route('/api/stats')
    def api_stats():
        stats = get_stats()
        alerts = []
        for config in get_running_configs():
            features, _ = get_feature_usage(config)
            for f in features:
                if f['total'] > 0 and f['used'] / f['total'] >= 0.85:
                    alerts.append(f"{config['name']}: {f['feature']} 使用率 {int(f['used']/f['total']*100)}%")
        stats['alerts'] = alerts
        return jsonify(stats)

    @app.route('/api/vendors/save', methods=['POST'])
    def api_vendor_save():
        vendor_id = request.form.get('id')
        daemon_name = request.form.get('daemon_name', '').strip()
        vendor_name = request.form.get('vendor_name', '').strip()
        default_path = request.form.get('default_daemon_path', '').strip()
        exclude_path = request.form.get('default_exclude_path', '').strip()
        host_id = request.form.get('host_id') or None

        if not daemon_name or not vendor_name:
            return jsonify({'success': False, 'message': 'Daemon 名称和厂商名称不能为空'})

        if vendor_id:
            update_vendor(int(vendor_id), daemon_name, vendor_name, default_path, exclude_path, host_id)
        else:
            save_vendor(daemon_name, vendor_name, default_path, exclude_path, host_id)

        return jsonify({'success': True, 'message': '厂商已保存'})

    @app.route('/api/vendors/<int:vendor_id>/delete', methods=['POST'])
    def api_vendor_delete(vendor_id):
        delete_vendor(vendor_id)
        return jsonify({'success': True, 'message': '厂商已删除'})

    @app.route('/api/config/<int:config_id>/command')
    def api_config_command(config_id):
        config = get_config(config_id)
        if not config:
            return jsonify({'success': False, 'message': '配置不存在'}), 404
        cmd = build_lmgrd_command(config)
        return jsonify({'success': True, 'command': cmd})

    # ===== Host Management =====

    @app.route('/api/hosts/save', methods=['POST'])
    def api_host_save():
        data = request.form.to_dict()
        if 'id' in data and data['id']:
            data['id'] = int(data['id'])
        else:
            data['id'] = None
        save_host(data)
        return jsonify({'success': True, 'message': '主机已保存'})

    @app.route('/api/hosts/<int:host_id>/delete', methods=['POST'])
    def api_host_delete(host_id):
        delete_host_record(host_id)
        return jsonify({'success': True, 'message': '主机已删除'})

    @app.route('/api/hosts/<int:host_id>/test', methods=['POST'])
    def api_host_test(host_id):
        host = get_host(host_id)
        if not host:
            return jsonify({'success': False, 'message': '主机不存在'}), 404
        import subprocess
        from app.host import update_host_status
        if host.get('auth_type') == 'password':
            password = host.get('auth_value', '')
            cmd = ['sshpass', '-p', password, 'ssh',
                   '-o', 'ConnectTimeout=5', '-o', 'StrictHostKeyChecking=no',
                   '-p', str(host.get('port', 22)),
                   f"{host['username']}@{host['hostname']}", 'hostname']
        else:
            cmd = ['ssh', '-o', 'ConnectTimeout=5', '-o', 'BatchMode=yes',
                   '-p', str(host.get('port', 22)),
                   f"{host['username']}@{host['hostname']}", 'hostname']
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                update_host_status(host_id, 'online')
                return jsonify({'success': True, 'message': f'连接成功: {result.stdout.strip()}'})
            else:
                update_host_status(host_id, 'offline')
                return jsonify({'success': False, 'message': f'SSH 失败: {result.stderr.strip() or result.stdout.strip()}'})
        except subprocess.TimeoutExpired:
            update_host_status(host_id, 'offline')
            return jsonify({'success': False, 'message': '连接超时'})
        except FileNotFoundError:
            return jsonify({'success': False, 'message': 'ssh 或 sshpass 命令不可用'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})

    # ===== Settings =====

    @app.route('/api/settings/save', methods=['POST'])
    def api_settings_save():
        for key, value in request.form.items():
            set_setting(key, value)
        return jsonify({'success': True, 'message': '设置已保存'})

    # ===== Backup / Restore =====

    @app.route('/api/backup/export')
    def api_backup_export():
        data = export_all()
        return jsonify(data)

    @app.route('/api/backup/import', methods=['POST'])
    def api_backup_import():
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': '未上传文件'})
        f = request.files['file']
        mode = request.form.get('mode', 'merge')
        try:
            data = json.loads(f.read())
            count = import_all(data, mode)
            return jsonify({'success': True, 'message': f'已导入 {count} 个表的数据'})
        except json.JSONDecodeError:
            return jsonify({'success': False, 'message': '文件格式错误,不是有效的 JSON'})
        except Exception as e:
            return jsonify({'success': False, 'message': f'导入失败: {e}'})

    # ===== Config Clone =====

    @app.route('/api/config/<int:config_id>/clone', methods=['POST'])
    def api_config_clone(config_id):
        config = get_config(config_id)
        if not config:
            return jsonify({'success': False, 'message': '配置不存在'}), 404
        new_name = request.form.get('name', config['name'] + '-clone')
        data = dict(config)
        data.pop('id', None)
        data.pop('created_at', None)
        data.pop('updated_at', None)
        data['name'] = new_name
        data['status'] = 'stopped'
        data['pid'] = None
        data['auto_start'] = 0

        from app.config import save_config as sc
        new_id = sc(data)
        add_log(new_name, 'CLONE', 'SUCCESS', f'从 {config["name"]} 克隆')
        return jsonify({'success': True, 'config_id': new_id, 'message': f'配置已克隆: {new_name}'})

    # ===== Usage Snapshot / Trends =====

    @app.route('/api/usage/snapshot')
    def api_usage_snapshot():
        from app.vendor import get_db
        configs = get_running_configs()
        conn = get_db()
        count = 0
        for c in configs:
            features, error = get_feature_usage(c)
            if error:
                continue
            for f in features:
                pct = round(f['used'] / f['total'] * 100, 1) if f['total'] > 0 else 0
                conn.execute(
                    'INSERT INTO usage_history (config_id, config_name, vendor_name, feature, total, used, pct) VALUES (?,?,?,?,?,?,?)',
                    (c['id'], c['name'], f.get('vendor', ''), f['feature'], f['total'], f['used'], pct)
                )
                count += 1
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': f'已记录 {count} 条用量快照'})

    @app.route('/api/usage/trends')
    def api_usage_trends():
        from app.vendor import get_db
        vendor = request.args.get('vendor', '')
        hours = request.args.get('hours', 24)
        conn = get_db()
        # Group by vendor: show each vendor's features as separate series
        if vendor:
            rows = conn.execute('''
                SELECT vendor_name, feature, recorded_at, pct FROM usage_history
                WHERE vendor_name = ? AND recorded_at > datetime('now', ?)
                ORDER BY recorded_at ASC
            ''', (vendor, f'-{hours} hours')).fetchall()
        else:
            rows = conn.execute('''
                SELECT vendor_name, feature, recorded_at, pct FROM usage_history
                WHERE recorded_at > datetime('now', ?)
                ORDER BY recorded_at ASC
            ''', (f'-{hours} hours',)).fetchall()
        conn.close()

        # Group by vendor -> feature -> data points
        vendors = {}
        for r in rows:
            vname = r['vendor_name'] or 'unknown'
            fname = r['feature']
            if vname not in vendors:
                vendors[vname] = {}
            if fname not in vendors[vname]:
                vendors[vname][fname] = []
            vendors[vname][fname].append({
                'time': r['recorded_at'],
                'pct': round(r['pct'], 1)
            })
        return jsonify({'success': True, 'vendors': vendors})

    @app.route('/api/usage/vendors')
    def api_usage_vendors():
        # Return vendors from vendors table (not from history, which may be empty)
        vendors = list_vendors()
        return jsonify({'success': True, 'vendors': [v['vendor_name'] for v in vendors]})

    # ===== Report Export =====

    @app.route('/api/report/csv')
    def api_report_csv():
        from app.vendor import get_db
        import csv, io
        conn = get_db()
        rows = conn.execute('''
            SELECT config_name, vendor_name, feature, total, used, pct, recorded_at
            FROM usage_history
            ORDER BY recorded_at DESC
            LIMIT 5000
        ''').fetchall()
        conn.close()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['配置名', '厂商', 'Feature', '总量', '使用中', '使用率%', '记录时间'])
        for r in rows:
            writer.writerow([r['config_name'], r['vendor_name'], r['feature'],
                           r['total'], r['used'], r['pct'], r['recorded_at']])
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=licman-report.csv'}
        )

    # ===== Notification Test =====

    @app.route('/api/notify/test', methods=['POST'])
    def api_notify_test():
        smtp = get_smtp_config()
        if not smtp['smtp_host'] or not smtp['to_addrs']:
            return jsonify({'success': False, 'message': '邮件未配置: 需要 SMTP 主机和收件人地址'})
        success, msg = send_email(
            subject='[LicMan] 测试邮件',
            body='这是 LicMan 的测试邮件。\n\n邮件通知配置正常。',
            **smtp
        )
        return jsonify({'success': success, 'message': msg})

    # ===== License Expiry =====

    @app.route('/api/config/<int:config_id>/expiry')
    def api_config_expiry(config_id):
        config = get_config(config_id)
        if not config:
            return jsonify({'success': False, 'message': '配置不存在'}), 404
        features, earliest, error = parse_license_expiry(config['license_file'])
        if error:
            return jsonify({'success': False, 'message': error})
        return jsonify({'success': True, 'features': features, 'earliest_days': earliest})

    @app.route('/api/expiry/alerts')
    def api_expiry_alerts():
        warn_days = int(get_setting('expire_warn_days') or 30)
        alerts = get_expiry_alerts(list_configs(), warn_days)
        return jsonify({'success': True, 'alerts': alerts})

    # ===== DAEMON Line Detection =====

    @app.route('/api/config/<int:config_id>/daemon-check')
    def api_daemon_check(config_id):
        config = get_config(config_id)
        if not config:
            return jsonify({'success': False, 'message': '配置不存在'}), 404

        vendor = None
        if config.get('vendor_id'):
            from app.vendor import get_vendor
            vendor = get_vendor(config['vendor_id'])

        daemon_name = vendor['daemon_name'] if vendor else ''
        daemon_path = config.get('daemon_path') or (vendor.get('default_daemon_path', '') if vendor else '')
        options_file = config.get('options_file', '')
        if not options_file and vendor:
            options_file = vendor.get('default_exclude_path', '')

        host = _get_host_for_config(config)
        info = detect_daemon_conflicts(
            config['license_file'], daemon_name, daemon_path, options_file, host=host
        )
        # Also check SERVER line
        server_info = detect_server_conflicts(config['license_file'], host=host)
        info['server_line'] = server_info.get('server_line')
        info['server_hostname'] = server_info.get('current_hostname')
        info['server_port'] = server_info.get('current_port')
        return jsonify({'success': True, **info})

    @app.route('/api/config/<int:config_id>/daemon-write', methods=['POST'])
    def api_daemon_write(config_id):
        config = get_config(config_id)
        if not config:
            return jsonify({'success': False, 'message': '配置不存在'}), 404

        vendor = None
        if config.get('vendor_id'):
            from app.vendor import get_vendor
            vendor = get_vendor(config['vendor_id'])

        daemon_name = vendor['daemon_name'] if vendor else ''
        daemon_path = config.get('daemon_path') or (vendor.get('default_daemon_path', '') if vendor else '')
        options_file = config.get('options_file', '')
        if not options_file and vendor:
            options_file = vendor.get('default_exclude_path', '')

        host = _get_host_for_config(config)
        success, message = force_write_daemon_line(
            config['license_file'], daemon_name, daemon_path, options_file, host=host
        )
        return jsonify({'success': success, 'message': message})

    # ===== Port Check =====

    @app.route('/api/config/<int:config_id>/port-check')
    def api_port_check(config_id):
        config = get_config(config_id)
        if not config:
            return jsonify({'success': False, 'message': '配置不存在'}), 404
        host = _get_host_for_config(config)
        port = parse_license_port(config['license_file'], host=host)
        if port is None:
            return jsonify({'success': False, 'message': '未在 SERVER 行找到端口号'})
        check_ip = host['hostname'] if host else '127.0.0.1'
        listening = check_port_listening(check_ip, port)
        return jsonify({
            'success': True,
            'port': port,
            'host': check_ip,
            'listening': listening,
            'message': f'{check_ip}:{port} {"已监听" if listening else "未监听"}'
        })

    # ===== License Preview =====

    @app.route('/api/config/license-preview', methods=['POST'])
    def api_license_preview():
        path = request.form.get('path', '')
        host_id = request.form.get('host_id', '')
        if not path:
            return jsonify({'success': False, 'content': '未提供路径'})
        host = get_host(int(host_id)) if host_id else None
        content = preview_license_file(path, max_lines=10, host=host)
        if content is None:
            return jsonify({'success': False, 'content': '文件不存在或无法读取 (如果是远程主机请检查 SSH 连接)'})
        return jsonify({'success': True, 'content': content})

    # ===== Log Tail (SSE) =====

    @app.route('/api/config/<int:config_id>/log/tail')
    def api_log_tail(config_id):
        config = get_config(config_id)
        if not config:
            return jsonify({'success': False, 'message': '配置不存在'}), 404

        log_path = config.get('log_path', '')
        if not log_path or not os.path.exists(log_path):
            return jsonify({'success': False, 'message': '未配置日志路径或文件不存在'}), 400

        def generate():
            try:
                with open(log_path, 'r') as f:
                    f.seek(0, 2)
                    while True:
                        line = f.readline()
                        if line:
                            yield f'data: {line}\n\n'
                        else:
                            time.sleep(1)
            except GeneratorExit:
                pass
        return Response(generate(), mimetype='text/event-stream', headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        })

    @app.route('/api/config/<int:config_id>/log/content')
    def api_log_content(config_id):
        """Return last N lines of the log file."""
        config = get_config(config_id)
        if not config:
            return jsonify({'success': False, 'message': '配置不存在'}), 404

        log_path = config.get('log_path', '')
        if not log_path or not os.path.exists(log_path):
            return jsonify({'success': False, 'message': '未配置日志路径或文件不存在'}), 400

        lines = request.args.get('lines', 200, type=int)
        try:
            with open(log_path, 'r') as f:
                all_lines = f.readlines()
                last = all_lines[-lines:] if len(all_lines) > lines else all_lines
                return jsonify({'success': True, 'content': ''.join(last), 'path': log_path})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})

    socketio.init_app(app)
    return app


# ===== SocketIO Terminal =====

@socketio.on('terminal-init')
def handle_terminal_init():
    """Spawn a bash shell with pty for this client."""
    sid = request.sid

    # Kill existing session if any
    if sid in _terminal_sessions:
        try:
            _terminal_sessions[sid]['fd']  # check it exists
        except Exception:
            pass

    pid, fd = pty.fork()
    if pid == 0:
        # Child: exec bash
        env = os.environ.copy()
        env['TERM'] = 'xterm-256color'
        os.execve('/bin/bash', ['/bin/bash'], env)
    else:
        # Parent: start reader thread
        _terminal_sessions[sid] = {'pid': pid, 'fd': fd}
        threading.Thread(target=_read_terminal, args=(sid, fd), daemon=True).start()


def _read_terminal(sid, fd):
    """Read from pty and send to client."""
    try:
        while True:
            r, _, _ = select.select([fd], [], [], 0.1)
            if r:
                data = os.read(fd, 4096)
                if data:
                    socketio.emit('terminal-output', data.decode('utf-8', errors='replace'), to=sid)
    except OSError:
        pass


@socketio.on('terminal-input')
def handle_terminal_input(data):
    """Receive keystrokes from client and write to pty."""
    sid = request.sid
    session = _terminal_sessions.get(sid)
    if session:
        try:
            os.write(session['fd'], data.encode('utf-8'))
        except OSError:
            pass


@socketio.on('terminal-resize')
def handle_terminal_resize(data):
    """Handle terminal resize from client."""
    sid = request.sid
    session = _terminal_sessions.get(sid)
    if session:
        rows = data.get('rows', 24)
        cols = data.get('cols', 80)
        try:
            import fcntl
            import struct
            import termios
            winsize = struct.pack('HHHH', rows, cols, 0, 0)
            fcntl.ioctl(session['fd'], termios.TIOCSWINSZ, winsize)
        except Exception:
            pass


@socketio.on('disconnect')
def handle_disconnect():
    """Clean up terminal on disconnect."""
    sid = request.sid
    session = _terminal_sessions.pop(sid, None)
    if session:
        try:
            os.close(session['fd'])
            os.kill(session['pid'], 9)
        except Exception:
            pass


# ===== Auto-start helpers =====

RC_LOCAL = '/etc/rc.local'


def _set_auto_start(config, enable):
    config_id = config.get('id')
    marker = f'# licman-config-{config_id}'

    try:
        with open(RC_LOCAL, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = ['#!/bin/bash\n', 'exit 0\n']

    lines = [l for l in lines if marker not in l]

    if enable:
        cmd = build_lmgrd_command(config)
        entry = f'{marker}\n{cmd} &\n'
        inserted = False
        for i, line in enumerate(lines):
            if line.strip().startswith('exit 0'):
                lines.insert(i, entry)
                inserted = True
                break
        if not inserted:
            lines.append(entry)

    with open(RC_LOCAL, 'w') as f:
        f.writelines(lines)
