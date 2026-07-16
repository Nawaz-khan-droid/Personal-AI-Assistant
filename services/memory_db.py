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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS search_cache (
                    query_key TEXT PRIMARY KEY,
                    result TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
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

    def delete_memory(self, key: str) -> bool:
        """Thread-safe delete operation. Returns True if a row was deleted."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_context WHERE key = ?", (key,))
            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()
            return deleted

    def get_all_memories(self) -> dict:
        """Fetches the entire key-value memory store as a dictionary."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM user_context")
            results = cursor.fetchall()
            conn.close()
            return {row[0]: row[1] for row in results}

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

    def set_search_cache(self, query_key: str, result: str):
        """Thread-safe write operation for search cache."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO search_cache (query_key, result, timestamp) VALUES (?, ?, CURRENT_TIMESTAMP)", 
                (query_key, result)
            )
            conn.commit()
            conn.close()

    def get_search_cache(self, query_key: str, max_age_hours: int = 24) -> str:
        """Thread-safe read operation for search cache with expiration."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT result FROM search_cache 
                WHERE query_key = ? AND timestamp >= datetime('now', ?)
            """, (query_key, f"-{max_age_hours} hours"))
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None

