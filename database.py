import sqlite3
from datetime import datetime

from config import DB_PATH


class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS smtp_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                host TEXT NOT NULL,
                port INTEGER NOT NULL,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                use_tls INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                recipients TEXT NOT NULL,
                status TEXT NOT NULL,
                sent_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def list_smtp_accounts(self):
        cursor = self.conn.execute("SELECT * FROM smtp_accounts ORDER BY id DESC")
        return cursor.fetchall()

    def add_smtp_account(self, name, host, port, username, password, use_tls):
        self.conn.execute(
            """
            INSERT INTO smtp_accounts (name, host, port, username, password, use_tls)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, host, int(port), username, password, int(use_tls)),
        )
        self.conn.commit()

    def update_smtp_account(self, account_id, name, host, port, username, password, use_tls):
        self.conn.execute(
            """
            UPDATE smtp_accounts
            SET name = ?, host = ?, port = ?, username = ?, password = ?, use_tls = ?
            WHERE id = ?
            """,
            (name, host, int(port), username, password, int(use_tls), account_id),
        )
        self.conn.commit()

    def delete_smtp_account(self, account_id):
        self.conn.execute("DELETE FROM smtp_accounts WHERE id = ?", (account_id,))
        self.conn.commit()

    def list_templates(self):
        cursor = self.conn.execute("SELECT * FROM templates ORDER BY id DESC")
        return cursor.fetchall()

    def add_template(self, name, subject, body):
        self.conn.execute(
            "INSERT INTO templates (name, subject, body) VALUES (?, ?, ?)",
            (name, subject, body),
        )
        self.conn.commit()

    def update_template(self, template_id, name, subject, body):
        self.conn.execute(
            """
            UPDATE templates
            SET name = ?, subject = ?, body = ?
            WHERE id = ?
            """,
            (name, subject, body, template_id),
        )
        self.conn.commit()

    def delete_template(self, template_id):
        self.conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))
        self.conn.commit()

    def list_contacts(self):
        cursor = self.conn.execute("SELECT * FROM contacts ORDER BY id DESC")
        return cursor.fetchall()

    def add_contact(self, name, email):
        self.conn.execute(
            "INSERT INTO contacts (name, email) VALUES (?, ?)",
            (name, email),
        )
        self.conn.commit()

    def delete_contact(self, contact_id):
        self.conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
        self.conn.commit()

    def add_history(self, subject, body, recipients, status):
        self.conn.execute(
            """
            INSERT INTO history (subject, body, recipients, status, sent_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (subject, body, recipients, status, datetime.utcnow().isoformat()),
        )
        self.conn.commit()

    def list_history(self):
        cursor = self.conn.execute("SELECT * FROM history ORDER BY id DESC")
        return cursor.fetchall()
