import sqlite3
import threading
from pathlib import Path

class LocalMemoryDB:
    """
    Synchronous, thread-safe SQLite wrapper serving as the Assistant's long-term memory.
    """
    def __init__(self):
        # Resolve the absolute path to the static directory
        project_root = Path(__file__).parent.parent
        db_dir = project_root / "core" / "static"
        db_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = db_dir / "memory.db"
        self._lock = threading.Lock()
        
        # Initialize the database schema safely
        self._init_db()

    def _init_db(self):
        with self._lock:
            # check_same_thread=False allows access across the ThreadPoolExecutor bounds
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_context (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()
            conn.close()

    def set_memory(self, key: str, value: str):
        """Thread-safe write operation."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO user_context (key, value) VALUES (?, ?)", 
                (key, value)
            )
            conn.commit()
            conn.close()

    def get_memory(self, key: str) -> str:
        """Thread-safe read operation."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM user_context WHERE key = ?", (key,))
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None

    def search_memory(self, search_query: str) -> list:
        """
        Queries the user_context table using a SQL LIKE operator 
        to fetch matching historical facts.
        """
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            cursor = conn.cursor()
            # Wrap the query string in wildcards for substring matching
            like_query = f"%{search_query}%"
            cursor.execute("SELECT value FROM user_context WHERE value LIKE ?", (like_query,))
            results = cursor.fetchall()
            conn.close()
            # Flatten the list of tuples into a clean list of strings
            return [row[0] for row in results]
