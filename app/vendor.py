import sqlite3
import os

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
DB_PATH = os.path.join(DB_DIR, 'licman.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            daemon_name TEXT NOT NULL,
            vendor_name TEXT NOT NULL,
            default_daemon_path TEXT,
            default_exclude_path TEXT,
            host_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            vendor_id INTEGER REFERENCES vendors(id),
            lmgrd_path TEXT NOT NULL,
            license_file TEXT NOT NULL,
            daemon_path TEXT,
            options_file TEXT,
            log_path TEXT,
            extra_args TEXT,
            auto_start INTEGER DEFAULT 0,
            status TEXT DEFAULT 'stopped',
            pid INTEGER,
            host_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_name TEXT NOT NULL,
            action TEXT NOT NULL,
            status TEXT NOT NULL,
            detail TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS hosts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            hostname TEXT NOT NULL,
            port INTEGER DEFAULT 22,
            username TEXT DEFAULT 'root',
            auth_type TEXT DEFAULT 'key',
            auth_value TEXT,
            status TEXT DEFAULT 'unknown',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS usage_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id INTEGER REFERENCES configs(id),
            config_name TEXT,
            vendor_name TEXT,
            feature TEXT NOT NULL,
            total INTEGER DEFAULT 0,
            used INTEGER DEFAULT 0,
            pct REAL DEFAULT 0,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    conn.close()

    # Migrate: add host_id if column missing
    _migrate_host_id()


def _migrate_host_id():
    conn = get_db()
    migrations = [
        ('configs', 'host_id', 'INTEGER'),
        ('vendors', 'default_exclude_path', 'TEXT'),
        ('vendors', 'host_id', 'INTEGER'),
    ]
    for table, col, _ in migrations:
        cols = [r[1] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()]
        if col not in cols:
            conn.execute(f'ALTER TABLE {table} ADD COLUMN {col} TEXT')
    conn.commit()
    conn.close()


def list_vendors():
    conn = get_db()
    rows = conn.execute('''
        SELECT v.*, h.name as host_name
        FROM vendors v
        LEFT JOIN hosts h ON v.host_id = h.id
        ORDER BY v.vendor_name
    ''').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_vendor(vendor_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM vendors WHERE id = ?', (vendor_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def save_vendor(daemon_name, vendor_name, default_daemon_path='', default_exclude_path='', host_id=None):
    conn = get_db()
    conn.execute(
        'INSERT INTO vendors (daemon_name, vendor_name, default_daemon_path, default_exclude_path, host_id) VALUES (?, ?, ?, ?, ?)',
        (daemon_name, vendor_name, default_daemon_path, default_exclude_path, host_id)
    )
    conn.commit()
    conn.close()


def update_vendor(vendor_id, daemon_name, vendor_name, default_daemon_path, default_exclude_path='', host_id=None):
    conn = get_db()
    conn.execute(
        'UPDATE vendors SET daemon_name=?, vendor_name=?, default_daemon_path=?, default_exclude_path=?, host_id=? WHERE id=?',
        (daemon_name, vendor_name, default_daemon_path, default_exclude_path, host_id, vendor_id)
    )
    conn.commit()
    conn.close()


def delete_vendor(vendor_id):
    conn = get_db()
    conn.execute('DELETE FROM vendors WHERE id = ?', (vendor_id,))
    conn.commit()
    conn.close()


def get_vendor_config_count(vendor_id):
    conn = get_db()
    row = conn.execute('SELECT COUNT(*) as cnt FROM configs WHERE vendor_id = ?', (vendor_id,)).fetchone()
    conn.close()
    return row['cnt']
