import sqlite3
from flask import Flask, make_response, render_template_string, request, send_file
import os
from admin import admin_bp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_FOLDER = os.path.join(BASE_DIR, "sdsfiles")
QR_FOLDER  = os.path.join(BASE_DIR, "qrcodes")
QR_FILENAME = "DLX SDS QR Sheet.pdf"
DB_PATH = os.path.join(BASE_DIR, "sds.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-prod")
app.register_blueprint(admin_bp)

# ── GHS pictogram labels ──────────────────────────────────────────────────────
GHS_ICONS = {
    "GHS01": "Explosive",
    "GHS02": "Flammable",
    "GHS03": "Oxidizing",
    "GHS04": "Compressed Gas",
    "GHS05": "Corrosive",
    "GHS06": "Toxic",
    "GHS07": "Irritant",
    "GHS08": "Health Hazard",
    "GHS09": "Environmental",
}

# ── Categories (display name → icon filename stem) ───────────────────────────
# Icons live at  /static/category_icons/<stem>.svg
# Any missing icon falls back to placeholder.svg via the onerror handler.
CATEGORIES = [
    ("Adhesives & Sealants",   "adhesives_sealants"),
    ("Aerosols",               "aerosols"),
    ("Antifreeze & Coolants",  "antifreeze_coolants"),
    ("Antiseptics",            "antiseptics"),
    ("Deodorizers",            "deodorizers"),
    ("Enamels & Lacquers",     "enamels_lacquers"),
    ("Fuels",                  "fuels"),
    ("Glass Cleaner",          "glass_cleaner"),
    ("Greases",                "greases"),
    ("Helium",                 "helium"),
    ("Hydraulic Fluids",       "hydraulic_fluids"),
    ("Ice Melt",               "ice_melt"),
    ("Lead Acid Batteries",    "lead_acid_batteries"),
    ("Leather Cleaner",        "leather_cleaner"),
    ("Lubricants",             "lubricants"),
    ("Mechanical Cleaners",    "mechanical_cleaners"),
    ("Motor Oils",             "motor_oils"),
    ("Nitrogen",               "nitrogen"),
    ("Oil Additives",          "oil_additives"),
    ("Paints & Solvents",      "paints_solvents"),
    ("Polishes & Waxes",       "polishes_waxes"),
    ("Soaps & Cleaners",       "soaps_cleaners"),
    ("Welding Gases",          "welding_gases"),
]

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

        /* ── Page layout ── */
        .page-body { display: flex; align-items: flex-start; }
        .left-margin {
            width: 180px;
            flex-shrink: 0;
            padding: 24px 16px;
            position: sticky;
            top: 64px;
            height: calc(100vh - 64px);
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        .btn-dl {
            display: flex;
            align-items: center;
            gap: 8px;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 10px 14px;
            color: var(--muted);
            text-decoration: none;
            font-size: 13px;
            font-weight: 500;
            font-family: 'DM Sans', sans-serif;
            transition: color 0.15s, border-color 0.15s, background 0.15s;
            width: 100%;
        }
        .btn-dl:hover { color: var(--text); border-color: var(--red); background: var(--surface); }
        .btn-dl svg { flex-shrink: 0; opacity: 0.7; }
        .main-content { flex: 1; min-width: 0; }

        /* ── Container ── */
        .container {
            max-width: 1020px;
            margin: 0 auto;
            padding: 24px 24px 48px;
        }

        /* ── View toggle bar ── */
        .view-bar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 10px;
        }
        .view-bar-label {
            font-size: 13px;
            color: var(--muted);
            font-family: 'DM Mono', monospace;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }
        .view-toggle { display: flex; gap: 6px; }
        .view-toggle a {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 500;
            text-decoration: none;
            border: 1px solid var(--border);
            color: var(--muted);
            background: var(--card);
            transition: color 0.15s, border-color 0.15s, background 0.15s;
        }
        .view-toggle a:hover { color: var(--text); border-color: var(--muted); }
        .view-toggle a.active { color: white; background: var(--red); border-color: var(--red); }

        /* ── Back link ── */
        .back-link {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 13px;
            color: var(--muted);
            text-decoration: none;
            margin-bottom: 4px;
            transition: color 0.15s;
        }
        .back-link:hover { color: var(--text); }

        /* ── Category heading (list view) ── */
        .category-heading {
            font-size: 20px;
            font-weight: 600;
            color: var(--accent);
            margin-bottom: 4px;
        }
        .category-subheading {
            font-size: 13px;
            color: var(--muted);
            font-family: 'DM Mono', monospace;
            margin-bottom: 20px;
        }

        /* ── Folder grid ── */
        .folder-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 12px;
        }
        .folder-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 18px 14px 14px;
            text-decoration: none;
            color: inherit;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 10px;
            transition: border-color 0.15s, box-shadow 0.15s;
        }
        .folder-card:hover {
            border-color: var(--red);
            box-shadow: 0 0 0 1px var(--red), 0 4px 16px rgba(0,0,0,0.3);
        }
        .folder-icon {
            width: 64px;
            height: 64px;
            border-radius: 10px;
            overflow: hidden;
            background: #222;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }
        .folder-icon img { width: 100%; height: 100%; object-fit: contain; }
        .folder-label {
            font-size: 12px;
            font-weight: 500;
            color: var(--accent);
            text-align: center;
            line-height: 1.35;
        }
        .folder-count {
            font-family: 'DM Mono', monospace;
            font-size: 11px;
            color: var(--muted);
        }

        /* ── SDS result cards ── */
        .results-meta {
            font-size: 12px;
            color: var(--muted);
            font-family: 'DM Mono', monospace;
            letter-spacing: 0.04em;
            margin-bottom: 16px;
            text-transform: uppercase;
        }
        .empty-state { text-align: center; padding: 64px 24px; color: var(--muted); }
        .empty-state p { font-size: 15px; margin-top: 8px; }

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
        .card-title { font-size: 15px; font-weight: 600; color: var(--accent); line-height: 1.3; }
        .card-preview { font-size: 13px; color: var(--muted); line-height: 1.6; grid-column: 1; }
        .card-meta {
            grid-column: 2; grid-row: 1 / 3;
            display: flex; flex-direction: column;
            align-items: flex-end; gap: 10px; min-width: 0;
        }
        .revision-date {
            font-family: 'DM Mono', monospace;
            font-size: 11px; color: var(--muted);
            letter-spacing: 0.04em; white-space: nowrap;
        }
        .revision-date span { color: #aaa; font-weight: 500; }

        /* ── GHS icons ── */
        .hazard-icons { display: flex; flex-wrap: wrap; gap: 4px; justify-content: flex-end; max-width: 140px; }
        .ghs-icon { width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; position: relative; }
        .ghs-icon img { max-width: 100%; max-height: 100%; }
        .ghs-icon:hover::after {
            content: attr(data-label);
            position: absolute; bottom: calc(100% + 4px); right: 0;
            background: #111; color: white; font-size: 11px;
            padding: 3px 7px; border-radius: 4px; white-space: nowrap;
            pointer-events: none; font-family: 'DM Sans', sans-serif; z-index: 10;
        }

        @media (max-width: 640px) {
            .left-margin { display: none; }
            .folder-grid { grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); }
        }
    </style>
</head>
<body>

<header>
    <h1>DLX SDS Database</h1>
    <span class="header-count">{{ total_count }} sheet{% if total_count != 1 %}s{% endif %}</span>
</header>

<form method="POST" action="/" class="search-wrap">
    <input class="search-input" type="text" name="query"
           placeholder="Search by product name or content…"
           value="{{ query }}" autofocus>
    <button class="btn-search" type="submit">Search</button>
    {% if query %}
        <a class="btn-clear" href="/">Clear</a>
    {% endif %}
</form>

<div class="page-body">

    <div class="left-margin">
        <a class="btn-dl" href="/download-qr" download>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            Download QR Code
        </a>
    </div>

    <div class="main-content">
    <div class="container">

        {% if query %}
        {# ────────────────── SEARCH RESULTS ────────────────── #}
            <div class="results-meta">
                {{ results|length }} result{% if results|length != 1 %}s{% endif %} for "{{ query }}"
            </div>
            {% if not results %}
                <div class="empty-state">
                    <p>No safety data sheets found for "{{ query }}".</p>
                </div>
            {% endif %}
            {% for row in results %}
                {% include '_sds_card.html' ignore missing %}
                <a class="card" href="/view/{{ row[0] }}">
                    <div class="card-title">{{ row[1].replace('.pdf','').replace('.PDF','') }}</div>
                    <div class="card-meta">
                        {% if row[3] %}<div class="revision-date">Rev. <span>{{ row[3] }}</span></div>
                        {% else %}<div class="revision-date" style="opacity:0.4">No date</div>{% endif %}
                        {% if row[4] %}
                            <div class="hazard-icons">
                                {% for code in row[4].split(',') %}
                                    {% if code.strip() in ghs_icons %}
                                        <div class="ghs-icon" data-label="{{ ghs_icons[code.strip()] }}">
                                            <img src="/static/ghs_svg/{{ code.strip() }}.svg" alt="{{ ghs_icons[code.strip()] }}">
                                        </div>
                                    {% endif %}
                                {% endfor %}
                            </div>
                        {% endif %}
                    </div>
                    <div class="card-preview">{{ row[2][:180] }}…</div>
                </a>
            {% endfor %}

        {% elif view == 'folder' %}
        {# ────────────────── FOLDER VIEW ────────────────── #}
            <div class="view-bar">
                <span class="view-bar-label">Safety Data Sheet Categories</span>
                <div class="view-toggle">
                    <a href="/?view=folder" class="active">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
                        Folder view
                    </a>
                    <a href="/?view=list">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
                        List view
                    </a>
                </div>
            </div>

            <div class="folder-grid">
                {% for cat_name, cat_stem, cat_count in categories %}
                <a class="folder-card" href="/?view=list&category={{ cat_name | urlencode }}">
                    <div class="folder-icon">
                        <img src="/static/category_icons/{{ cat_stem }}.svg"
                             onerror="this.onerror=null;this.src='/static/category_icons/placeholder.svg'"
                             alt="{{ cat_name }}">
                    </div>
                    <div class="folder-label">{{ cat_name }}</div>
                    <div class="folder-count">{{ cat_count }} sheet{% if cat_count != 1 %}s{% endif %}</div>
                </a>
                {% endfor %}
            </div>

        {% else %}
        {# ────────────────── LIST VIEW ────────────────── #}
            <div class="view-bar">
                <div>
                    {% if category %}
                        <a class="back-link" href="/?view=folder">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
                            All categories
                        </a>
                    {% else %}
                        <span class="view-bar-label">All Sheets</span>
                    {% endif %}
                </div>
                <div class="view-toggle">
                    <a href="/?view=folder">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
                        Folder view
                    </a>
                    <a href="/?view=list" class="active">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
                        List view
                    </a>
                </div>
            </div>

            {% if category %}
                <div class="category-heading">{{ category }}</div>
                <div class="category-subheading">{{ results|length }} sheet{% if results|length != 1 %}s{% endif %}</div>
            {% else %}
                <div class="results-meta">{{ results|length }} sheet{% if results|length != 1 %}s{% endif %} total</div>
            {% endif %}

            {% if not results %}
                <div class="empty-state">
                    <p>No safety data sheets found{% if category %} in this category{% endif %}.</p>
                </div>
            {% endif %}

            {% for row in results %}
            <a class="card" href="/view/{{ row[0] }}">
                <div class="card-title">{{ row[1].replace('.pdf','').replace('.PDF','') }}</div>
                <div class="card-meta">
                    {% if row[3] %}<div class="revision-date">Rev. <span>{{ row[3] }}</span></div>
                    {% else %}<div class="revision-date" style="opacity:0.4">No date</div>{% endif %}
                    {% if row[4] %}
                        <div class="hazard-icons">
                            {% for code in row[4].split(',') %}
                                {% if code.strip() in ghs_icons %}
                                    <div class="ghs-icon" data-label="{{ ghs_icons[code.strip()] }}">
                                        <img src="/static/ghs_svg/{{ code.strip() }}.svg" alt="{{ ghs_icons[code.strip()] }}">
                                    </div>
                                {% endif %}
                            {% endfor %}
                        </div>
                    {% endif %}
                </div>
                <div class="card-preview">{{ row[2][:180] }}…</div>
            </a>
            {% endfor %}

        {% endif %}

    </div>{# end .container #}
    </div>{# end .main-content #}
</div>{# end .page-body #}

</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def home():
    query       = ""
    results     = []
    view        = request.args.get("view", "folder")
    category    = request.args.get("category", "").strip()
    categories_data = []

    try:
        conn   = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM sds")
        total_count = cursor.fetchone()[0]

        if request.method == "POST":
            # Full-text search overrides view/category
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
            results = cursor.fetchall()

        elif view == "folder":
            cursor.execute("SELECT category, COUNT(*) FROM sds GROUP BY category")
            counts = dict(cursor.fetchall())
            for cat_name, cat_stem in CATEGORIES:
                categories_data.append((cat_name, cat_stem, counts.get(cat_name, 0)))

        else:
            # List view — optionally filtered by category
            if category:
                cursor.execute(
                    "SELECT id, file_name, content, revision_date, hazard_codes FROM sds WHERE category = ? ORDER BY file_name",
                    (category,)
                )
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
        view=view,
        category=category,
        categories=categories_data,
        total_count=total_count,
        ghs_icons=GHS_ICONS,
    )


@app.route("/pdf/<int:sds_id>")
def get_pdf(sds_id):
    try:
        conn   = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT file_name FROM sds WHERE id = ?", (sds_id,))
        result = cursor.fetchone()
    finally:
        conn.close()

    if not result:
        return "File not found in DB", 404

    filename  = result[0]
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
        <a href="javascript:history.back()">← Back</a>
    </div>
    <iframe src="/pdf/{sds_id}"></iframe>
</body>
</html>"""


@app.route("/download-qr")
def download_qr():
    file_path = os.path.join(QR_FOLDER, QR_FILENAME)
    if not os.path.exists(file_path):
        return "QR code file not found", 404
    return send_file(file_path, mimetype="application/pdf", as_attachment=True, download_name=QR_FILENAME)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)