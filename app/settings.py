from app.vendor import get_db


DEFAULTS = {
    'expire_warn_days': '30',
    'global_exclude_dir': '',
}


def get_setting(key):
    conn = get_db()
    row = conn.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
    conn.close()
    if row:
        return row['value']
    return DEFAULTS.get(key, '')


def set_setting(key, value):
    conn = get_db()
    conn.execute(
        'INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)',
        (key, value)
    )
    conn.commit()
    conn.close()


def get_all_settings():
    result = dict(DEFAULTS)
    conn = get_db()
    rows = conn.execute('SELECT key, value FROM settings').fetchall()
    conn.close()
    for r in rows:
        result[r['key']] = r['value']
    return result
