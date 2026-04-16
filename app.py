import sqlite3
from unittest import result

from flask import Flask, render_template_string, request, send_file, send_from_directory
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_FOLDER = BASE_DIR
DB_PATH = os.path.join(BASE_DIR, "sds.db")

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>SDS Database</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #222222;
            margin: 0;
        }

        header {
            background-color: #8A191B;
            color: black;
            padding: 20px;
            text-align: center;
        }

        .container {
            padding: 20px;
        }

        form {
            margin-bottom: 20px;
            text-align: center;
        }

        input[type="text"] {
            padding: 8px;
            width: 300px;
        }

        button {
            padding: 8px 12px;
            background-color: #3498db;
            color: white;
            border: none;
            cursor: pointer;
        }

        a.clear {
            margin-left: 10px;
            text-decoration: none;
            color: #e74c3c;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            background: white;
        }

        th, td {
            padding: 10px;
            border-bottom: 1px solid #ddd;
            text-align: left;
        }

        th {
            background-color: #ecf0f1;
        }

        tr:hover {
            background-color: #f1f1f1;
        }
    </style>
</head>
<body>

<header>
    <h1>DLX SDS Database</h1>
</header>

<div class="container">

    <form method="POST">
        <input type="text" name="query" placeholder="Search SDS..." value="{{ query }}">
        <button type="submit">Search</button>
        <a href="/" class="clear">Clear</a>
    </form>

<ul style="list-style: none; padding: 0;">
    {% for row in results %}
        <li style="background: white; margin-bottom: 10px; padding: 15px; border-radius: 5px;">
            
            <!-- Clean file name (no .pdf) -->
            <strong>
                <a href="/view/{{ row[0] }}">
                    {{ row[1].replace('.pdf', '') }}
                </a>
            </strong>

            <br><br>

            <!-- Preview of content -->
            <small>
                {{ row[2][:200] }}...
            </small>

        </li>
    {% endfor %}
</ul>

</div>

</body>
</html>
"""

@app.route("/view/<int:sds_id>")
def view_sds(sds_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT file_name FROM sds WHERE id = ?", (sds_id,))
    result = cursor.fetchone()
    conn.close()

    if not result:
        return "File not found in DB", 404

    filename = result[0]

    file_path = os.path.join(PDF_FOLDER, filename)

    if not os.path.exists(file_path):
        return f"Missing file: {file_path}", 404

    return send_file(file_path, mimetype="application/pdf")

@app.route("/view/<int:sds_id>")
def view_sds(sds_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT file_path FROM sds WHERE id = ?", (sds_id,))
    result = cursor.fetchone()
    file_path = os.path.join(BASE_DIR, result[0]) 

    if not os.path.exists(file_path): 
        return f"File not found: {file_path}", 404

    return send_from_directory (PDF_FOLDER, result [0], mimetype="application/pdf")

    conn.close()

if __name__ == "__main__":
        port = int(os.environ.get("PORT", 8000))
        app.run(host="0.0.0.0", port=port, debug=False)