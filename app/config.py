from app.vendor import get_db


def list_configs():
    conn = get_db()
    rows = conn.execute('''
        SELECT c.*, v.vendor_name, v.daemon_name, h.name as host_name, h.hostname as host_hostname
        FROM configs c
        LEFT JOIN vendors v ON c.vendor_id = v.id
        LEFT JOIN hosts h ON c.host_id = h.id
        ORDER BY c.updated_at DESC
    ''').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_config(config_id):
    conn = get_db()
    row = conn.execute('''
        SELECT c.*, v.vendor_name, v.daemon_name, h.name as host_name, h.hostname as host_hostname
        FROM configs c
        LEFT JOIN vendors v ON c.vendor_id = v.id
        LEFT JOIN hosts h ON c.host_id = h.id
        WHERE c.id = ?
    ''', (config_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def save_config(data):
    conn = get_db()
    if data.get('id'):
        conn.execute('''
            UPDATE configs SET name=?, vendor_id=?, lmgrd_path=?, license_file=?,
                daemon_path=?, options_file=?, log_path=?, extra_args=?,
                auto_start=?, host_id=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        ''', (
            data['name'], data.get('vendor_id'), data['lmgrd_path'], data['license_file'],
            data.get('daemon_path', ''), data.get('options_file', ''),
            data.get('log_path', ''), data.get('extra_args', ''),
            data.get('auto_start', 0), data.get('host_id'), data['id']
        ))
        config_id = data['id']
    else:
        cur = conn.execute('''
            INSERT INTO configs (name, vendor_id, lmgrd_path, license_file,
                daemon_path, options_file, log_path, extra_args, auto_start, host_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['name'], data.get('vendor_id'), data['lmgrd_path'], data['license_file'],
            data.get('daemon_path', ''), data.get('options_file', ''),
            data.get('log_path', ''), data.get('extra_args', ''),
            data.get('auto_start', 0), data.get('host_id')
        ))
        config_id = cur.lastrowid
    conn.commit()
    conn.close()
    return config_id


def delete_config(config_id):
    conn = get_db()
    conn.execute('DELETE FROM configs WHERE id = ?', (config_id,))
    conn.commit()
    conn.close()


def update_config_status(config_id, status, pid=None):
    conn = get_db()
    if pid is not None:
        conn.execute('UPDATE configs SET status=?, pid=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                     (status, pid, config_id))
    else:
        conn.execute('UPDATE configs SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                     (status, config_id))
    conn.commit()
    conn.close()


def get_running_configs():
    conn = get_db()
    rows = conn.execute('''
        SELECT c.*, v.vendor_name, v.daemon_name, h.name as host_name
        FROM configs c
        LEFT JOIN vendors v ON c.vendor_id = v.id
        LEFT JOIN hosts h ON c.host_id = h.id
        WHERE c.status = 'running'
    ''').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def build_lmgrd_command(config):
    """Build the lmgrd command line from config."""
    parts = [config['lmgrd_path']]
    if config.get('license_file'):
        parts.extend(['-c', config['license_file']])
    if config.get('log_path'):
        parts.extend(['-l', config['log_path']])
    if config.get('extra_args'):
        parts.append(config['extra_args'])
    return ' '.join(parts)
