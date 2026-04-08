from database import DatabaseManager


def test_database_tables():
    db = DatabaseManager()
    assert db.list_smtp_accounts() == []
    assert db.list_templates() == []
    assert db.list_contacts() == []
    assert db.list_history() == []


if __name__ == "__main__":
    test_database_tables()
    print("All tests passed.")
