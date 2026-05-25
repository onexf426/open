"""Backup and restore all licman configuration."""
import json
import os
from datetime import datetime
from app.vendor import get_db


def export_all():
    """Export all database tables as a JSON-serializable dict."""
    conn = get_db()
    data = {'version': 1, 'exported_at': datetime.now().isoformat(), 'tables': {}}

    for table in ['vendors', 'configs', 'hosts', 'settings', 'logs']:
        rows = conn.execute(f'SELECT * FROM {table}').fetchall()
        data['tables'][table] = [dict(r) for r in rows]

    conn.close()
    return data


def import_all(data, mode='merge'):
    """Import backup data. mode: 'merge' (upsert) or 'replace' (clear first)."""
    tables_data = data.get('tables', {})
    conn = get_db()

    if mode == 'replace':
        for table in tables_data:
            conn.execute(f'DELETE FROM {table}')

    for table, rows in tables_data.items():
        if not rows:
            continue
        columns = list(rows[0].keys())
        placeholders = ','.join(['?' for _ in columns])
        # Remove 'id' for auto-increment
        non_id_cols = [c for c in columns if c != 'id']
        non_id_ph = ','.join(['?' for _ in non_id_cols])

        for row in rows:
            values = [row.get(c) for c in non_id_cols]
            if 'id' in columns and table not in ('settings',):
                # Try update by id first
                existing = conn.execute(
                    f'SELECT id FROM {table} WHERE id=?', (row['id'],)
                ).fetchone()
                if existing:
                    set_clause = ','.join([f'{c}=?' for c in non_id_cols])
                    conn.execute(
                        f'UPDATE {table} SET {set_clause} WHERE id=?',
                        values + [row['id']]
                    )
                    continue
            conn.execute(
                f'INSERT OR IGNORE INTO {table} ({",".join(non_id_cols)}) VALUES ({non_id_ph})',
                values
            )

    conn.commit()
    conn.close()
    return len(tables_data)


def backup_license_files(backup_dir):
    """Copy all referenced license files to a backup directory."""
    import shutil
    from app.config import list_configs

    configs = list_configs()
    copied = 0
    for c in configs:
        lic = c.get('license_file', '')
        log = c.get('log_path', '')
        opts = c.get('options_file', '')
        for fpath in [lic, log, opts]:
            if fpath and os.path.exists(fpath):
                dest = os.path.join(backup_dir, os.path.basename(fpath))
                shutil.copy2(fpath, dest)
                copied += 1
    return copied
