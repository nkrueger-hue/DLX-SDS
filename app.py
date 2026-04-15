from flask import send_from_directory
import os

PDF_FOLDER = os.path.join(BASE_DIR, "data", "pdfs")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "sds.db")

return send_from_directory (PDF_FOLDER, result [0], mimetype="application/pdf")

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

@app.route("/", methods=["GET", "POST"])
def index():
    query = request.form.get("query", "").strip() if request.method == "POST" else ""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if query:
        cursor.execute("""
            SELECT * FROM sds
            WHERE file_name LIKE ?
            OR content LIKE ?
            ORDER BY file_name ASC
        """, (f"%{query}%", f"%{query}%"))
    else:
        cursor.execute("SELECT * FROM sds ORDER BY file_name ASC")

    results = cursor.fetchall()
    conn.close()

    return render_template_string(HTML, results=results, query=query)

@app.route("/view/<int:sds_id>")
def view_sds(sds_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT file_path FROM sds WHERE id = ?", (sds_id,))
    result = cursor.fetchone()

    conn.close()

file_path = os.path.join(BASE_DIR, result[0])

if not os.path.exists(file_path):
    return f"File not found: {file_path}", 404

    return send_file(file_path, mimetype="application/pdf")

if __name__ == "__main__":
        port = int(os.environ.get("PORT", 8000))
        app.run(host="0.0.0.0", port=port)
        app.run(debug=False)
