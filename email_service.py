import smtplib
from email.mime.text import MIMEText


class EmailService:
    def __init__(self, host, port, username, password, use_tls=True):
        self.host = host
        self.port = int(port)
        self.username = username
        self.password = password
        self.use_tls = bool(use_tls)

    def _connect(self):
        server = smtplib.SMTP(self.host, self.port, timeout=20)
        server.ehlo()
        if self.use_tls:
            server.starttls()
            server.ehlo()
        server.login(self.username, self.password)
        return server

    def test_connection(self):
        server = self._connect()
        server.quit()
        return True

    def send_email(self, subject, body, recipients):
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = self.username
        msg["To"] = ", ".join(recipients)

        server = self._connect()
        server.sendmail(self.username, recipients, msg.as_string())
        server.quit()
