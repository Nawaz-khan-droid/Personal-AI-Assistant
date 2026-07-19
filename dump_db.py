import sqlite3

def dump_db():
    conn = sqlite3.connect('c:\\Projects\\jarvis voice assistant\\jarvis-assistant\\core\\static\\memory.db')
    cursor = conn.cursor()
    
    print("--- MEMORY FACTS ---")
    cursor.execute("SELECT * FROM user_context;")
    for row in cursor.fetchall():
        print(f"{row[0]}: {row[1]}")
        
    print("\n--- SEARCH CACHE ---")
    cursor.execute("SELECT query_key, timestamp FROM search_cache;")
    for row in cursor.fetchall():
        print(f"[{row[1]}] Query: {row[0]}")
        
    conn.close()

if __name__ == '__main__':
    dump_db()
