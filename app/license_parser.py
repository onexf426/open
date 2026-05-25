import re
from datetime import datetime, date
from app.remote import remote_read_file


def parse_license_expiry(license_file_path, host=None):
    """Parse a FlexLM license file and extract feature expiry dates.
    Returns (features, earliest_date, error).
    """
    features = []
    earliest = None
    error = None

    content, error = remote_read_file(host, license_file_path)
    if error:
        return [], None, error

    # Match INCREMENT/FEATURE lines: keyword feature vendor version exp-date ...
    # Format: INCREMENT|FEATURE name vendor version exp-date {dd-mmm-yyyy} ...
    pattern = r'^(?:INCREMENT|FEATURE)\s+(\S+)\s+\S+\s+\S+\s+(\d{1,2}-\w{3,4}-\d{4})'

    perpetual_pattern = r'^(?:INCREMENT|FEATURE)\s+(\S+)\s+\S+\s+\S+\s+(?:permanent|uncounted)'

    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('#') or not line:
            continue

        # Check for perpetual/permanent
        pm = re.search(perpetual_pattern, line, re.IGNORECASE)
        if pm:
            features.append({
                'feature': pm.group(1),
                'exp_date': 'permanent',
                'expired': False,
                'days_left': None
            })
            continue

        m = re.search(pattern, line, re.IGNORECASE)
        if m:
            name = m.group(1)
            date_str = m.group(2)
            try:
                exp_date = datetime.strptime(date_str, '%d-%b-%Y').date()
            except ValueError:
                try:
                    exp_date = datetime.strptime(date_str, '%d-%B-%Y').date()
                except ValueError:
                    continue

            days_left = (exp_date - date.today()).days
            features.append({
                'feature': name,
                'exp_date': date_str,
                'expired': days_left < 0,
                'days_left': days_left
            })
            if earliest is None or (days_left is not None and days_left < earliest):
                earliest = days_left

    return features, earliest, error


def get_expiry_alerts(configs, warn_days=30):
    """Check all configs for expiring licenses. Returns one alert per config (earliest expiry)."""
    alerts = []
    for c in configs:
        lic_file = c.get('license_file', '')
        if not lic_file:
            continue
        features, earliest, _ = parse_license_expiry(lic_file)
        # Find the earliest expiring feature for this config
        worst = None
        for f in features:
            days = f.get('days_left')
            if days is not None and days >= 0 and days <= warn_days:
                if worst is None or days < worst['days_left']:
                    worst = {
                        'config_name': c['name'],
                        'config_id': c.get('id'),
                        'daemon_name': c.get('daemon_name', ''),
                        'feature': f['feature'],
                        'exp_date': f['exp_date'],
                        'days_left': days
                    }
            elif f.get('expired'):
                if worst is None or worst.get('days_left', 0) >= 0:
                    worst = {
                        'config_name': c['name'],
                        'config_id': c.get('id'),
                        'daemon_name': c.get('daemon_name', ''),
                        'feature': f['feature'],
                        'exp_date': f['exp_date'],
                        'days_left': -1,
                        'expired': True
                    }
        if worst:
            alerts.append(worst)
    return alerts
