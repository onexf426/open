"""Email notification for license alerts."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(smtp_host, smtp_port, username, password, to_addrs, subject, body):
    """Send an email via SMTP. Returns (success, message)."""
    msg = MIMEMultipart()
    msg['From'] = username
    msg['To'] = ', '.join(to_addrs) if isinstance(to_addrs, list) else to_addrs
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, int(smtp_port), timeout=15)
        elif smtp_port == 25:
            server = smtplib.SMTP(smtp_host, int(smtp_port), timeout=15)
        else:
            server = smtplib.SMTP(smtp_host, int(smtp_port), timeout=15)
            server.ehlo()
            if server.has_extn('STARTTLS'):
                server.starttls()
                server.ehlo()
        server.login(username, password)
        server.sendmail(username, to_addrs, msg.as_string())
        server.quit()
        return True, '邮件已发送'
    except smtplib.SMTPAuthenticationError:
        return False, 'SMTP 认证失败,请检查邮箱和密码/授权码'
    except smtplib.SMTPConnectError:
        return False, f'无法连接 SMTP 服务器 {smtp_host}:{smtp_port}'
    except Exception as e:
        return False, str(e)


def get_smtp_config():
    """Return keyword-argument dict usable as send_email(**config, subject=..., body=...)."""
    from app.settings import get_all_settings
    s = get_all_settings()
    return {
        'smtp_host': s.get('smtp_host', ''),
        'smtp_port': int(s.get('smtp_port', '587')),
        'username': s.get('smtp_user', ''),
        'password': s.get('smtp_pass', ''),
        'to_addrs': [addr.strip() for addr in s.get('smtp_to', '').split(',') if addr.strip()],
    }
