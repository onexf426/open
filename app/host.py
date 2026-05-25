from app.vendor import get_db


def list_hosts():
    conn = get_db()
    rows = conn.execute('SELECT * FROM hosts ORDER BY name').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_host(host_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM hosts WHERE id = ?', (host_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def save_host(data):
    conn = get_db()
    host_id = data.get('id')
    if host_id:
        conn.execute('''
            UPDATE hosts SET name=?, hostname=?, port=?, username=?,
                auth_type=?, auth_value=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        ''', (
            data['name'], data['hostname'], data.get('port', 22),
            data.get('username', 'root'), data.get('auth_type', 'key'),
            data.get('auth_value', ''), host_id
        ))
    else:
        cur = conn.execute('''
            INSERT INTO hosts (name, hostname, port, username, auth_type, auth_value)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            data['name'], data['hostname'], data.get('port', 22),
            data.get('username', 'root'), data.get('auth_type', 'key'),
            data.get('auth_value', '')
        ))
        host_id = cur.lastrowid
    conn.commit()
    conn.close()
    return host_id


def delete_host(host_id):
    conn = get_db()
    conn.execute('UPDATE configs SET host_id = NULL WHERE host_id = ?', (host_id,))
    conn.execute('DELETE FROM hosts WHERE id = ?', (host_id,))
    conn.commit()
    conn.close()


def update_host_status(host_id, status):
    conn = get_db()
    conn.execute('UPDATE hosts SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                 (status, host_id))
    conn.commit()
    conn.close()
