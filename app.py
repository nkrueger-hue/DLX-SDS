import sqlite3
from flask import Flask, make_response, render_template_string, request, send_file
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_FOLDER = BASE_DIR
DB_PATH = os.path.join(BASE_DIR, "sds.db")

app = Flask(__name__)

# ── GHS pictogram SVG icons ───────────────────────────────────────────────────
# Official GHS diamond format: white diamond, red fill, white inner field, black symbol.

GHS_ICONS = {
    "GHS01": ("Explosive", ),

    "GHS02": ("Flammable", ),

    "GHS03": ("Oxidizing", ),

    "GHS04": ("Compressed Gas", ),

    "GHS05": ("Corrosive", ),

    "GHS06": ("Toxic", ),

    "GHS07": ("Irritant", ),

    "GHS08": ("Health Hazard", ),

    "GHS09": ("Environmental", ),
}

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SDS Database</title>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        :root {
            --red:      #8A191B;
            --red-dark: #6b1315;
            --bg:       #1a1a1a;
            --surface:  #242424;
            --card:     #2c2c2c;
            --border:   #3a3a3a;
            --text:     #f0f0f0;
            --muted:    #888;
            --accent:   #e8e0d0;
        }

        body {
            font-family: 'DM Sans', sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
        }

        /* ── Header ── */
        header {
            background: var(--red);
            padding: 0 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            height: 64px;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 2px 12px rgba(0,0,0,0.4);
        }
        header h1 {
            font-size: 18px;
            font-weight: 600;
            letter-spacing: 0.04em;
            color: white;
            text-transform: uppercase;
        }
        .header-count {
            font-family: 'DM Mono', monospace;
            font-size: 12px;
            color: rgba(255,255,255,0.6);
            letter-spacing: 0.06em;
        }

        /* ── Search bar ── */
        .search-wrap {
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            padding: 16px 24px;
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .search-input {
            flex: 1;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 10px 16px;
            font-family: 'DM Sans', sans-serif;
            font-size: 15px;
            color: var(--text);
            outline: none;
            transition: border-color 0.15s;
        }
        .search-input::placeholder { color: var(--muted); }
        .search-input:focus { border-color: var(--red); }
        .btn-search {
            background: var(--red);
            color: white;
            border: none;
            border-radius: 8px;
            padding: 10px 20px;
            font-family: 'DM Sans', sans-serif;
            font-size: 15px;
            font-weight: 500;
            cursor: pointer;
            transition: background 0.15s;
        }
        .btn-search:hover { background: var(--red-dark); }
        .btn-clear {
            background: transparent;
            color: var(--muted);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 10px 16px;
            font-family: 'DM Sans', sans-serif;
            font-size: 14px;
            cursor: pointer;
            text-decoration: none;
            transition: color 0.15s, border-color 0.15s;
        }
        .btn-clear:hover { color: var(--text); border-color: var(--muted); }

        /* ── Results ── */
        .container {
            max-width: 960px;
            margin: 0 auto;
            padding: 24px 24px 48px;
        }
        .results-meta {
            font-size: 12px;
            color: var(--muted);
            font-family: 'DM Mono', monospace;
            letter-spacing: 0.04em;
            margin-bottom: 16px;
            text-transform: uppercase;
        }
        .empty-state {
            text-align: center;
            padding: 64px 24px;
            color: var(--muted);
        }
        .empty-state p { font-size: 15px; margin-top: 8px; }

        /* ── Result card ── */
        .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 18px 20px;
            margin-bottom: 10px;
            display: grid;
            grid-template-columns: 1fr auto;
            grid-template-rows: auto auto;
            gap: 8px 16px;
            transition: border-color 0.15s, box-shadow 0.15s;
            text-decoration: none;
            color: inherit;
        }
        .card:hover {
            border-color: var(--red);
            box-shadow: 0 0 0 1px var(--red), 0 4px 16px rgba(0,0,0,0.3);
        }
        .card-title {
            font-size: 15px;
            font-weight: 600;
            color: var(--accent);
            line-height: 1.3;
        }
        .card-preview {
            font-size: 13px;
            color: var(--muted);
            line-height: 1.6;
            grid-column: 1;
        }
        .card-meta {
            grid-column: 2;
            grid-row: 1 / 3;
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 10px;
            min-width: 0;
        }
        .revision-date {
            font-family: 'DM Mono', monospace;
            font-size: 11px;
            color: var(--muted);
            letter-spacing: 0.04em;
            white-space: nowrap;
        }
        .revision-date span {
            color: #aaa;
            font-weight: 500;
        }

        /* ── GHS icons ── */
        .hazard-icons {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            justify-content: flex-end;
            max-width: 140px;
        }
        .ghs-icon {
            width: 36px;
            height: 36px;
            flex-shrink: 0;
            position: relative;
        }
        .ghs-icon svg {
            width: 100%;
            height: 100%;
        }
        .ghs-icon:hover::after {
            content: attr(data-label);
            position: absolute;
            bottom: calc(100% + 4px);
            right: 0;
            background: #111;
            color: white;
            font-size: 11px;
            padding: 3px 7px;
            border-radius: 4px;
            white-space: nowrap;
            pointer-events: none;
            font-family: 'DM Sans', sans-serif;
            z-index: 10;
        }
    </style>
</head>
<body>

<header>
    <h1>DLX SDS Database</h1>
    <span class="header-count">{{ results|length }} result{% if results|length != 1 %}s{% endif %}</span>
</header>

<form method="POST" class="search-wrap">
    <input class="search-input" type="text" name="query"
           placeholder="Search by product name or content…"
           value="{{ query }}" autofocus>
    <button class="btn-search" type="submit">Search</button>
    {% if query %}
        <a class="btn-clear" href="/">Clear</a>
    {% endif %}
</form>

<div class="container">

    {% if query %}
        <div class="results-meta">{{ results|length }} result{% if results|length != 1 %}s{% endif %} for "{{ query }}"</div>
    {% endif %}

    {% if not results %}
        <div class="empty-state">
            <div style="font-size:32px;">🔍</div>
            <p>No safety data sheets found{% if query %} for "{{ query }}"{% endif %}.</p>
        </div>
    {% endif %}

    {% for row in results %}
        {# row: id, file_name, content, revision_date, hazard_codes #}
        <a class="card" href="/view/{{ row[0] }}">

            <div class="card-title">{{ row[1].replace('.pdf', '').replace('.PDF', '') }}</div>

            <div class="card-meta">
                {% if row[3] %}
                    <div class="revision-date">Rev. <span>{{ row[3] }}</span></div>
                {% else %}
                    <div class="revision-date" style="opacity:0.4">No date</div>
                {% endif %}

                {% if row[4] %}
                    <div class="hazard-icons">
                        {% for code in row[4].split(',') %}
                            {% if code.strip() in ghs_icons %}
                                <div class="ghs-icon" data-label="{{ ghs_icons[code.strip()][0] }}">
                                    <img src="static/ghs_svg/{{ code.strip() }}.svg">
                                </div>
                            {% endif %}
                        {% endfor %}
                    </div>
                {% endif %}
            </div>

            <div class="card-preview">{{ row[2][:180] }}…</div>

        </a>
    {% endfor %}

</div>

</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def home():
    query = ""
    results = []

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        if request.method == "POST":
            query = request.form.get("query", "").strip()
            cursor.execute("""
                SELECT id, file_name, content, revision_date, hazard_codes,
                    CASE
                        WHEN file_name LIKE ? THEN 1
                        WHEN content   LIKE ? THEN 2
                        ELSE 3
                    END as rank
                FROM sds
                WHERE file_name LIKE ? OR content LIKE ?
                ORDER BY rank, file_name
            """, (f"%{query}%",) * 4)
        else:
            cursor.execute(
                "SELECT id, file_name, content, revision_date, hazard_codes FROM sds ORDER BY file_name"
            )

        results = cursor.fetchall()
    finally:
        conn.close()

    return render_template_string(
        HTML,
        results=results,
        query=query,
        ghs_icons=GHS_ICONS,
    )


@app.route("/pdf/<int:sds_id>")
def get_pdf(sds_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT file_name FROM sds WHERE id = ?", (sds_id,))
        result = cursor.fetchone()
    finally:
        conn.close()

    if not result:
        return "File not found in DB", 404

    filename = result[0]
    file_path = os.path.join(PDF_FOLDER, filename)

    if not os.path.exists(file_path):
        return f"Missing file: {file_path}", 404

    response = make_response(send_file(file_path, mimetype="application/pdf"))
    response.headers["Content-Disposition"] = f"inline; filename={filename}"
    return response


@app.route("/view/<int:sds_id>")
def view_sds(sds_id):
    return f"""<!DOCTYPE html>
<html>
<head>
    <title>SDS Viewer</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ background: #1a1a1a; }}
        .topbar {{
            background: #8A191B;
            height: 44px;
            display: flex;
            align-items: center;
            padding: 0 16px;
            gap: 12px;
        }}
        .topbar a {{
            color: rgba(255,255,255,0.8);
            text-decoration: none;
            font-family: 'DM Sans', sans-serif;
            font-size: 14px;
        }}
        .topbar a:hover {{ color: white; }}
        iframe {{ width: 100%; height: calc(100vh - 44px); border: none; display: block; }}
    </style>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">
</head>
<body>
    <div class="topbar">
        <a href="/">← Back to Database</a>
    </div>
    <iframe src="/pdf/{sds_id}"></iframe>
</body>
</html>"""


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)