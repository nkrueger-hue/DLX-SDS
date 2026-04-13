import sqlite3

conn = sqlite3.connect("sds.db")
cursor = conn.cursor()

cursor.execute("SELECT file_name FROM sds")
rows = cursor.fetchall()

for row in rows:
    print(row)

conn.close()