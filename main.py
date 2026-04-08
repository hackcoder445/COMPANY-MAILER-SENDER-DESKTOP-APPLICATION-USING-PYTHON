import csv
import logging
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import APP_NAME, APP_VERSION, LOG_PATH
from database import DatabaseManager
from email_service import EmailService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)

logger = logging.getLogger("mailer")


class EmailWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, service, subject, body, recipients):
        super().__init__()
        self.service = service
        self.subject = subject
        self.body = body
        self.recipients = recipients

    def run(self):
        try:
            total = len(self.recipients)
            if total == 0:
                self.failed.emit("No recipients selected.")
                return
            for idx, recipient in enumerate(self.recipients, start=1):
                self.service.send_email(self.subject, self.body, [recipient])
                percent = int((idx / total) * 100)
                self.progress.emit(percent)
            self.finished.emit("Emails sent successfully.")
        except Exception as exc:
            self.failed.emit(str(exc))


class SendEmailTab(QWidget):
    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db
        self.worker = None
        self._build_ui()
        self.refresh_accounts()

    def _build_ui(self):
        layout = QVBoxLayout()

        account_row = QHBoxLayout()
        self.account_combo = QComboBox()
        self.test_button = QPushButton("Test Connection")
        self.test_button.clicked.connect(self.test_connection)
        account_row.addWidget(QLabel("SMTP Account:"))
        account_row.addWidget(self.account_combo, 1)
        account_row.addWidget(self.test_button)

        form = QGridLayout()
        self.subject_input = QLineEdit()
        self.body_input = QTextEdit()
        form.addWidget(QLabel("Subject:"), 0, 0)
        form.addWidget(self.subject_input, 0, 1)
        form.addWidget(QLabel("Email Body:"), 1, 0, Qt.AlignmentFlag.AlignTop)
        form.addWidget(self.body_input, 1, 1)

        recipients_group = QGroupBox("Recipients")
        recipients_layout = QVBoxLayout()
        self.recipients_list = QListWidget()
        controls = QHBoxLayout()
        self.add_recipient = QPushButton("Add")
        self.remove_recipient = QPushButton("Remove")
        self.load_csv = QPushButton("Load CSV")
        self.add_recipient.clicked.connect(self.add_recipient_manual)
        self.remove_recipient.clicked.connect(self.remove_selected_recipient)
        self.load_csv.clicked.connect(self.load_csv_recipients)
        controls.addWidget(self.add_recipient)
        controls.addWidget(self.remove_recipient)
        controls.addWidget(self.load_csv)
        recipients_layout.addWidget(self.recipients_list)
        recipients_layout.addLayout(controls)
        recipients_group.setLayout(recipients_layout)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.send_button = QPushButton("Send Emails")
        self.send_button.clicked.connect(self.send_emails)

        layout.addLayout(account_row)
        layout.addLayout(form)
        layout.addWidget(recipients_group)
        layout.addWidget(self.progress)
        layout.addWidget(self.send_button)
        self.setLayout(layout)

    def refresh_accounts(self):
        self.account_combo.clear()
        for row in self.db.list_smtp_accounts():
            self.account_combo.addItem(f"{row['name']} ({row['username']})", row)

    def add_recipient_manual(self):
        email, ok = QFileDialog.getOpenFileName(
            self, "Select a CSV or Cancel", str(Path.cwd()), "CSV Files (*.csv)"
        )
        if ok and email:
            return
        text, ok = QMessageBox.getText(self, "Add Recipient", "Email address:")
        if ok and text:
            self.recipients_list.addItem(text.strip())

    def remove_selected_recipient(self):
        for item in self.recipients_list.selectedItems():
            self.recipients_list.takeItem(self.recipients_list.row(item))

    def load_csv_recipients(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select recipients CSV", str(Path.cwd()), "CSV Files (*.csv)"
        )
        if not path:
            return
        with open(path, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                email = row.get("email") or row.get("Email") or row.get("EMAIL")
                if email:
                    self.recipients_list.addItem(email.strip())

    def test_connection(self):
        account = self.account_combo.currentData()
        if not account:
            QMessageBox.warning(self, "No account", "Add an SMTP account first.")
            return
        service = EmailService(
            account["host"],
            account["port"],
            account["username"],
            account["password"],
            account["use_tls"],
        )
        try:
            service.test_connection()
            QMessageBox.information(self, "Success", "Connection successful.")
        except Exception as exc:
            QMessageBox.critical(self, "Failed", str(exc))

    def send_emails(self):
        account = self.account_combo.currentData()
        if not account:
            QMessageBox.warning(self, "No account", "Add an SMTP account first.")
            return
        subject = self.subject_input.text().strip()
        body = self.body_input.toPlainText().strip()
        recipients = [
            self.recipients_list.item(i).text()
            for i in range(self.recipients_list.count())
        ]
        if not subject or not body:
            QMessageBox.warning(self, "Missing info", "Subject and body are required.")
            return
        service = EmailService(
            account["host"],
            account["port"],
            account["username"],
            account["password"],
            account["use_tls"],
        )
        self.send_button.setEnabled(False)
        self.progress.setValue(0)
        self.worker = EmailWorker(service, subject, body, recipients)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self._on_send_success)
        self.worker.failed.connect(self._on_send_failed)
        self.worker.start()

    def _on_send_success(self, message):
        self.send_button.setEnabled(True)
        self.db.add_history(
            self.subject_input.text().strip(),
            self.body_input.toPlainText().strip(),
            ", ".join(
                [
                    self.recipients_list.item(i).text()
                    for i in range(self.recipients_list.count())
                ]
            ),
            "success",
        )
        QMessageBox.information(self, "Done", message)

    def _on_send_failed(self, error):
        self.send_button.setEnabled(True)
        QMessageBox.critical(self, "Failed", error)


class TemplatesTab(QWidget):
    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db
        self.selected_id = None
        self._build_ui()
        self.refresh_templates()

    def _build_ui(self):
        layout = QHBoxLayout()
        self.list = QListWidget()
        self.list.itemClicked.connect(self.load_template)

        form = QVBoxLayout()
        self.name_input = QLineEdit()
        self.subject_input = QLineEdit()
        self.body_input = QTextEdit()
        save_btn = QPushButton("Save")
        delete_btn = QPushButton("Delete")
        save_btn.clicked.connect(self.save_template)
        delete_btn.clicked.connect(self.delete_template)

        form.addWidget(QLabel("Template Name"))
        form.addWidget(self.name_input)
        form.addWidget(QLabel("Subject"))
        form.addWidget(self.subject_input)
        form.addWidget(QLabel("Body"))
        form.addWidget(self.body_input)
        form.addWidget(save_btn)
        form.addWidget(delete_btn)

        layout.addWidget(self.list, 1)
        layout.addLayout(form, 2)
        self.setLayout(layout)

    def refresh_templates(self):
        self.list.clear()
        for row in self.db.list_templates():
            item = QListWidgetItem(row["name"])
            item.setData(Qt.ItemDataRole.UserRole, row)
            self.list.addItem(item)

    def load_template(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        self.selected_id = data["id"]
        self.name_input.setText(data["name"])
        self.subject_input.setText(data["subject"])
        self.body_input.setText(data["body"])

    def save_template(self):
        name = self.name_input.text().strip()
        subject = self.subject_input.text().strip()
        body = self.body_input.toPlainText().strip()
        if not name or not subject:
            QMessageBox.warning(self, "Missing info", "Name and subject are required.")
            return
        if self.selected_id:
            self.db.update_template(self.selected_id, name, subject, body)
        else:
            self.db.add_template(name, subject, body)
        self.refresh_templates()

    def delete_template(self):
        if not self.selected_id:
            return
        self.db.delete_template(self.selected_id)
        self.selected_id = None
        self.name_input.clear()
        self.subject_input.clear()
        self.body_input.clear()
        self.refresh_templates()


class ContactsTab(QWidget):
    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db
        self._build_ui()
        self.refresh_contacts()

    def _build_ui(self):
        layout = QVBoxLayout()
        self.list = QListWidget()
        actions = QHBoxLayout()
        add_btn = QPushButton("Add")
        remove_btn = QPushButton("Remove")
        import_btn = QPushButton("Import CSV")
        add_btn.clicked.connect(self.add_contact)
        remove_btn.clicked.connect(self.remove_contact)
        import_btn.clicked.connect(self.import_contacts)
        actions.addWidget(add_btn)
        actions.addWidget(remove_btn)
        actions.addWidget(import_btn)
        layout.addWidget(self.list)
        layout.addLayout(actions)
        self.setLayout(layout)

    def refresh_contacts(self):
        self.list.clear()
        for row in self.db.list_contacts():
            self.list.addItem(f"{row['name'] or ''} <{row['email']}>")

    def add_contact(self):
        name, ok = QMessageBox.getText(self, "Add Contact", "Name:")
        if not ok:
            return
        email, ok = QMessageBox.getText(self, "Add Contact", "Email:")
        if ok and email:
            self.db.add_contact(name.strip(), email.strip())
            self.refresh_contacts()

    def remove_contact(self):
        for item in self.list.selectedItems():
            self.list.takeItem(self.list.row(item))

    def import_contacts(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import contacts CSV", str(Path.cwd()), "CSV Files (*.csv)"
        )
        if not path:
            return
        with open(path, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                email = row.get("email") or row.get("Email")
                name = row.get("name") or row.get("Name") or ""
                if email:
                    self.db.add_contact(name.strip(), email.strip())
        self.refresh_contacts()


class SettingsTab(QWidget):
    def __init__(self, db: DatabaseManager, on_update):
        super().__init__()
        self.db = db
        self.on_update = on_update
        self.selected_id = None
        self._build_ui()
        self.refresh_accounts()

    def _build_ui(self):
        layout = QVBoxLayout()
        self.list = QListWidget()
        self.list.itemClicked.connect(self.load_account)
        form = QGridLayout()
        self.name_input = QLineEdit()
        self.host_input = QLineEdit()
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.tls_combo = QComboBox()
        self.tls_combo.addItems(["Yes", "No"])

        form.addWidget(QLabel("Name"), 0, 0)
        form.addWidget(self.name_input, 0, 1)
        form.addWidget(QLabel("Host"), 1, 0)
        form.addWidget(self.host_input, 1, 1)
        form.addWidget(QLabel("Port"), 2, 0)
        form.addWidget(self.port_input, 2, 1)
        form.addWidget(QLabel("Username"), 3, 0)
        form.addWidget(self.username_input, 3, 1)
        form.addWidget(QLabel("Password"), 4, 0)
        form.addWidget(self.password_input, 4, 1)
        form.addWidget(QLabel("Use TLS"), 5, 0)
        form.addWidget(self.tls_combo, 5, 1)

        actions = QHBoxLayout()
        save_btn = QPushButton("Save")
        delete_btn = QPushButton("Delete")
        save_btn.clicked.connect(self.save_account)
        delete_btn.clicked.connect(self.delete_account)
        actions.addWidget(save_btn)
        actions.addWidget(delete_btn)

        layout.addWidget(self.list)
        layout.addLayout(form)
        layout.addLayout(actions)
        self.setLayout(layout)

    def refresh_accounts(self):
        self.list.clear()
        for row in self.db.list_smtp_accounts():
            item = QListWidgetItem(row["name"])
            item.setData(Qt.ItemDataRole.UserRole, row)
            self.list.addItem(item)

    def load_account(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        self.selected_id = data["id"]
        self.name_input.setText(data["name"])
        self.host_input.setText(data["host"])
        self.port_input.setValue(data["port"])
        self.username_input.setText(data["username"])
        self.password_input.setText(data["password"])
        self.tls_combo.setCurrentText("Yes" if data["use_tls"] else "No")

    def save_account(self):
        name = self.name_input.text().strip()
        host = self.host_input.text().strip()
        port = self.port_input.value()
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        use_tls = self.tls_combo.currentText() == "Yes"
        if not name or not host or not username:
            QMessageBox.warning(self, "Missing info", "Name, host, and username required.")
            return
        if self.selected_id:
            self.db.update_smtp_account(
                self.selected_id, name, host, port, username, password, use_tls
            )
        else:
            self.db.add_smtp_account(name, host, port, username, password, use_tls)
        self.refresh_accounts()
        self.on_update()

    def delete_account(self):
        if not self.selected_id:
            return
        self.db.delete_smtp_account(self.selected_id)
        self.selected_id = None
        self.refresh_accounts()
        self.on_update()


class HistoryTab(QWidget):
    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db
        layout = QVBoxLayout()
        self.list = QListWidget()
        layout.addWidget(self.list)
        self.setLayout(layout)
        self.refresh_history()

    def refresh_history(self):
        self.list.clear()
        for row in self.db.list_history():
            self.list.addItem(
                f"{row['sent_at']} | {row['status']} | {row['subject']}"
            )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1100, 700)

        font = QFont("Segoe UI", 10)
        QApplication.instance().setFont(font)

        tabs = QTabWidget()
        self.send_tab = SendEmailTab(self.db)
        self.templates_tab = TemplatesTab(self.db)
        self.contacts_tab = ContactsTab(self.db)
        self.settings_tab = SettingsTab(self.db, self.send_tab.refresh_accounts)
        self.history_tab = HistoryTab(self.db)

        tabs.addTab(self.send_tab, "Send Email")
        tabs.addTab(self.templates_tab, "Templates")
        tabs.addTab(self.contacts_tab, "Contacts")
        tabs.addTab(self.settings_tab, "Settings")
        tabs.addTab(self.history_tab, "History")
        self.setCentralWidget(tabs)


def main():
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
