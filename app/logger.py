from app.vendor import get_db


def add_log(config_name, action, status, detail=''):
    conn = get_db()
    conn.execute(
        'INSERT INTO logs (config_name, action, status, detail) VALUES (?, ?, ?, ?)',
        (config_name, action, status, detail)
    )
    conn.commit()
    conn.close()


def get_logs(limit=100, offset=0):
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM logs ORDER BY created_at DESC LIMIT ? OFFSET ?',
        (limit, offset)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_log_count():
    conn = get_db()
    row = conn.execute('SELECT COUNT(*) as cnt FROM logs').fetchone()
    conn.close()
    return row['cnt']


def get_stats():
    conn = get_db()
    total = conn.execute('SELECT COUNT(*) as cnt FROM configs').fetchone()['cnt']
    running = conn.execute("SELECT COUNT(*) as cnt FROM configs WHERE status='running'").fetchone()['cnt']
    stopped = total - running
    conn.close()
    return {'total': total, 'running': running, 'stopped': stopped}
