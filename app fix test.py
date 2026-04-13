conn = sqlite3.connect("sds.db")
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(sds)")
print(cursor.fetchall())

conn.close()