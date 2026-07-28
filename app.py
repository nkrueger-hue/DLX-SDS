import sqlite3
from flask import Flask, make_response, render_template_string, request, send_file, redirect, jsonify
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
    ("3D Printing Materials",   "3d_printing_materials"),
    ("Adhesives & Sealants",    "adhesives_sealants"),
    ("Aerosols",                "aerosols"),
    ("Antifreeze & Coolants",   "antifreeze_coolants"),
    ("Antiseptics",             "antiseptics"),
    ("Brake Fluids",            "brake_fluids"),
    ("Carpet & Fabric Cleaners","carpet_fabric_cleaners"),
    ("Compressed Gases",        "compressed_gases"),
    ("Degreasers",              "degreasers"),
    ("Fuels",                   "fuels"),
    ("Glass Cleaners",          "glass_cleaners"),
    ("Greases",                 "greases"),
    ("Hydraulic Fluids",        "hydraulic_fluids"),
    ("Ice Melt",                "ice_melt"),
    ("Lubricants",              "lubricants"),
    ("Motor Oils",              "motor_oils"),
    ("Paints & Solvents",       "paints_solvents"),
    ("Pest Control",            "pest_control:"),
    ("Polishes & Waxes",        "polishes_waxes"),
    ("Protective Coatings",     "protective_coatings"),
    ("Refrigerants",            "refrigerants"),
    ("Rust Inhibitors",         "rust_inhibitors"),
    ("Shop Supplies",           "shop_supplies"),
    ("Soaps & Cleaners",        "soaps_cleaners"),
    ("Strippers & Removers",    "strippers_removers"),
    ("Transmission Fluids",     "transmission_fluids"),
    ("Welding Gases",           "welding_gases"),
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
        <a class="btn-dl" href="/inventory">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>
                <rect x="9" y="3" width="6" height="4" rx="1"/>
                <line x1="9" y1="12" x2="15" y2="12"/>
                <line x1="9" y1="16" x2="13" y2="16"/>
            </svg>
            Chemical Inventory
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


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, file_name, revision_date, hazard_codes, category
        FROM sds
        WHERE file_name LIKE ? OR content LIKE ?
        ORDER BY
            CASE WHEN file_name LIKE ? THEN 1 ELSE 2 END,
            file_name
        LIMIT 5
    """, (f"%{q}%", f"%{q}%", f"%{q}%"))
    rows = cursor.fetchall()
    conn.close()

    results = [
        {
            "id": row[0],
            "productName": row[1].replace(".pdf", "").replace(".PDF", ""),
            "revisionDate": row[2],
            "hazardCodes": row[3],
            "category": row[4],
            "pdfPath": f"/pdf/{row[0]}"
        }
        for row in rows
    ]
    return jsonify({"results": results})
    
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


INVENTORY_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chemical Inventory – SDS Database</title>
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
            --green:    #2a7a4b;
        }
        body { font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }

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
        .header-left { display: flex; align-items: center; gap: 16px; }
        header h1 { font-size: 18px; font-weight: 600; letter-spacing: 0.04em; color: white; text-transform: uppercase; }
        .header-back {
            color: rgba(255,255,255,0.75);
            text-decoration: none;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 5px;
            transition: color 0.15s;
        }
        .header-back:hover { color: white; }
        .header-count { font-family: 'DM Mono', monospace; font-size: 12px; color: rgba(255,255,255,0.6); letter-spacing: 0.06em; }

        .toolbar {
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            padding: 14px 24px;
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }
        .search-input {
            flex: 1;
            min-width: 200px;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 9px 14px;
            font-family: 'DM Sans', sans-serif;
            font-size: 14px;
            color: var(--text);
            outline: none;
            transition: border-color 0.15s;
        }
        .search-input::placeholder { color: var(--muted); }
        .search-input:focus { border-color: var(--red); }
        .btn {
            border: none;
            border-radius: 8px;
            padding: 9px 18px;
            font-family: 'DM Sans', sans-serif;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: background 0.15s, color 0.15s;
        }
        .btn-primary { background: var(--red); color: white; }
        .btn-primary:hover { background: var(--red-dark); }
        .btn-secondary { background: var(--card); color: var(--muted); border: 1px solid var(--border); }
        .btn-secondary:hover { color: var(--text); border-color: var(--muted); }
        .btn-danger { background: transparent; color: #c0392b; border: 1px solid #c0392b33; font-size: 12px; padding: 5px 10px; border-radius: 6px; }
        .btn-danger:hover { background: #c0392b22; }
        .btn-edit { background: transparent; color: var(--muted); border: 1px solid var(--border); font-size: 12px; padding: 5px 10px; border-radius: 6px; }
        .btn-edit:hover { color: var(--text); border-color: var(--muted); }

        .container { max-width: 1100px; margin: 0 auto; padding: 28px 24px 60px; }

        /* ── Stats strip ── */
        .stats-strip {
            display: flex;
            gap: 12px;
            margin-bottom: 24px;
            flex-wrap: wrap;
        }
        .stat-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 14px 20px;
            min-width: 140px;
        }
        .stat-label { font-size: 11px; color: var(--muted); font-family: 'DM Mono', monospace; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
        .stat-value { font-size: 22px; font-weight: 600; color: var(--accent); }

        /* ── Table ── */
        .table-wrap {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
        }
        table { width: 100%; border-collapse: collapse; }
        thead { background: var(--surface); }
        th {
            padding: 12px 16px;
            text-align: left;
            font-size: 11px;
            font-family: 'DM Mono', monospace;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
        }
        td {
            padding: 13px 16px;
            font-size: 14px;
            border-bottom: 1px solid var(--border);
            vertical-align: middle;
        }
        tr:last-child td { border-bottom: none; }
        tr:hover td { background: rgba(255,255,255,0.02); }
        .col-name { font-weight: 500; color: var(--accent); }
        .col-location { color: var(--muted); font-size: 13px; }
        .col-qty { font-family: 'DM Mono', monospace; font-size: 13px; }
        .col-actions { text-align: right; white-space: nowrap; display: flex; gap: 6px; justify-content: flex-end; }
        .sds-link {
            font-size: 12px;
            color: var(--red);
            text-decoration: none;
            font-weight: 500;
            white-space: nowrap;
        }
        .sds-link:hover { text-decoration: underline; }
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 20px;
            font-size: 11px;
            font-family: 'DM Mono', monospace;
            background: var(--surface);
            border: 1px solid var(--border);
            color: var(--muted);
        }
        .badge-low { border-color: #c0392b55; color: #e74c3c; background: #c0392b11; }
        .empty-state { text-align: center; padding: 60px 24px; color: var(--muted); font-size: 15px; }

        /* ── Flash messages ── */
        .flash { padding: 12px 20px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; }
        .flash-success { background: #1a3a2a; border: 1px solid #2a7a4b; color: #5cb85c; }
        .flash-error   { background: #3a1a1a; border: 1px solid #7a2a2a; color: #e74c3c; }

        /* ── Modal ── */
        .modal-backdrop {
            display: none;
            position: fixed; inset: 0;
            background: rgba(0,0,0,0.65);
            z-index: 200;
            align-items: center;
            justify-content: center;
        }
        .modal-backdrop.open { display: flex; }
        .modal {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 28px;
            width: 100%;
            max-width: 500px;
            box-shadow: 0 8px 40px rgba(0,0,0,0.6);
        }
        .modal h2 { font-size: 17px; font-weight: 600; margin-bottom: 20px; color: var(--accent); }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; font-size: 12px; color: var(--muted); font-family: 'DM Mono', monospace; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 6px; }
        .form-control {
            width: 100%;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 9px 13px;
            font-family: 'DM Sans', sans-serif;
            font-size: 14px;
            color: var(--text);
            outline: none;
            transition: border-color 0.15s;
        }
        .form-control:focus { border-color: var(--red); }
        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .form-actions { display: flex; gap: 10px; justify-content: flex-end; margin-top: 22px; }

        select.form-control option { background: var(--card); }

        @media (max-width: 640px) {
            .form-row { grid-template-columns: 1fr; }
            th:nth-child(3), td:nth-child(3) { display: none; }
        }
    </style>
</head>
<body>

<header>
    <div class="header-left">
        <a class="header-back" href="/">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
            SDS Database
        </a>
        <h1>Chemical Inventory</h1>
    </div>
    <span class="header-count">{{ total }} item{% if total != 1 %}s{% endif %}</span>
</header>

<form method="GET" action="/inventory" class="toolbar">
    <input class="search-input" type="text" name="q" placeholder="Search chemicals, locations…" value="{{ search_q }}">
    <button class="btn btn-primary" type="submit">Search</button>
    {% if search_q %}
        <a class="btn btn-secondary" href="/inventory">Clear</a>
    {% endif %}
    <button class="btn btn-primary" type="button" onclick="openModal()">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        Add Chemical
    </button>
</form>

<div class="container">

    {% if flash_msg %}
        <div class="flash flash-{{ flash_type }}">{{ flash_msg }}</div>
    {% endif %}

    <!-- Stats -->
    <div class="stats-strip">
        <div class="stat-card">
            <div class="stat-label">Total Items</div>
            <div class="stat-value">{{ total }}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Locations</div>
            <div class="stat-value">{{ location_count }}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Low Stock</div>
            <div class="stat-value" style="color:{% if low_stock_count > 0 %}#e74c3c{% else %}var(--accent){% endif %}">{{ low_stock_count }}</div>
        </div>
    </div>

    <!-- Table -->
    {% if not items %}
        <div class="empty-state">
            {% if search_q %}No chemicals found matching "{{ search_q }}".{% else %}No chemicals in inventory yet. Click <strong>Add Chemical</strong> to get started.{% endif %}
        </div>
    {% else %}
    <div class="table-wrap">
        <table>
            <thead>
                <tr>
                    <th>Chemical Name</th>
                    <th>Location</th>
                    <th>Quantity</th>
                    <th>Unit</th>
                    <th>SDS</th>
                    <th>Notes</th>
                    <th></th>
                </tr>
            </thead>
            <tbody>
                {% for item in items %}
                <tr>
                    <td class="col-name">{{ item[1] }}</td>
                    <td class="col-location">{{ item[2] or '—' }}</td>
                    <td class="col-qty">
                        {% if item[3] is not none %}
                            {{ item[3] }}
                            {% if item[5] and item[3] <= item[5] %}
                                <span class="badge badge-low">Low</span>
                            {% endif %}
                        {% else %}—{% endif %}
                    </td>
                    <td><span class="badge">{{ item[4] or '—' }}</span></td>
                    <td>
                        {% if item[6] %}
                            <a class="sds-link" href="/view/{{ item[6] }}" target="_blank">View SDS</a>
                        {% else %}—{% endif %}
                    </td>
                    <td class="col-location" style="max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="{{ item[7] or '' }}">{{ item[7] or '—' }}</td>
                    <td>
                        <div class="col-actions">
                            <button class="btn-edit btn" onclick="openEditModal({{ item[0] }}, {{ item|tojson }})">Edit</button>
                            <form method="POST" action="/inventory/delete/{{ item[0] }}" style="display:inline" onsubmit="return confirm('Delete this item?')">
                                <button class="btn-danger btn" type="submit">Delete</button>
                            </form>
                        </div>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% endif %}

</div>

<!-- Add/Edit Modal -->
<div class="modal-backdrop" id="modal" onclick="if(event.target===this)closeModal()">
    <div class="modal">
        <h2 id="modal-title">Add Chemical</h2>
        <form method="POST" id="modal-form" action="/inventory/add">
            <input type="hidden" name="item_id" id="field-id">
            <div class="form-group">
                <label>Chemical Name *</label>
                <input class="form-control" type="text" name="name" id="field-name" required placeholder="e.g. Isopropyl Alcohol">
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Location</label>
                    <input class="form-control" type="text" name="location" id="field-location" list="location-suggestions" placeholder="e.g. Cabinet A, Shelf 2">
                    <datalist id="location-suggestions">
                        {% for loc in locations %}
                            <option value="{{ loc }}">
                        {% endfor %}
                    </datalist>
                </div>
                <div class="form-group">
                    <label>Quantity</label>
                    <input class="form-control" type="number" name="quantity" id="field-quantity" step="0.01" min="0" placeholder="0">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Unit</label>
                    <select class="form-control" name="unit" id="field-unit">
                        <option value="">— select —</option>
                        <option>gal</option>
                        <option>L</option>
                        <option>mL</option>
                        <option>oz</option>
                        <option>fl oz</option>
                        <option>lb</option>
                        <option>kg</option>
                        <option>g</option>
                        <option>drum</option>
                        <option>pail</option>
                        <option>can</option>
                        <option>bottle</option>
                        <option>case</option>
                        <option>unit</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Low-Stock Alert At</label>
                    <input class="form-control" type="number" name="low_stock_threshold" id="field-threshold" step="0.01" min="0" placeholder="e.g. 1">
                </div>
            </div>
            <div class="form-group">
                <label>Link to SDS (optional)</label>
                <select class="form-control" name="sds_id" id="field-sds">
                    <option value="">— none —</option>
                    {% for sds in sds_list %}
                        <option value="{{ sds[0] }}">{{ sds[1].replace('.pdf','').replace('.PDF','') }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-group">
                <label>Notes</label>
                <input class="form-control" type="text" name="notes" id="field-notes" placeholder="Storage conditions, supplier, etc.">
            </div>
            <div class="form-actions">
                <button class="btn btn-secondary" type="button" onclick="closeModal()">Cancel</button>
                <button class="btn btn-primary" type="submit">Save</button>
            </div>
        </form>
    </div>
</div>

<script>
function openModal() {
    document.getElementById('modal-title').textContent = 'Add Chemical';
    document.getElementById('modal-form').action = '/inventory/add';
    document.getElementById('field-id').value = '';
    ['name','location','quantity','notes'].forEach(f => document.getElementById('field-'+f).value = '');
    document.getElementById('field-unit').value = '';
    document.getElementById('field-threshold').value = '';
    document.getElementById('field-sds').value = '';
    document.getElementById('modal').classList.add('open');
}
function openEditModal(id, item) {
    document.getElementById('modal-title').textContent = 'Edit Chemical';
    document.getElementById('modal-form').action = '/inventory/edit/' + id;
    document.getElementById('field-id').value = id;
    document.getElementById('field-name').value = item[1] || '';
    document.getElementById('field-location').value = item[2] || '';
    document.getElementById('field-quantity').value = item[3] !== null ? item[3] : '';
    document.getElementById('field-unit').value = item[4] || '';
    document.getElementById('field-threshold').value = item[5] !== null ? item[5] : '';
    document.getElementById('field-sds').value = item[6] || '';
    document.getElementById('field-notes').value = item[7] || '';
    document.getElementById('modal').classList.add('open');
}
function closeModal() {
    document.getElementById('modal').classList.remove('open');
}
document.addEventListener('keydown', e => { if(e.key === 'Escape') closeModal(); });
</script>

</body>
</html>
"""


def init_inventory_db():
    """Create the chemical_inventory table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chemical_inventory (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            name                TEXT NOT NULL,
            location            TEXT,
            quantity            REAL,
            unit                TEXT,
            low_stock_threshold REAL,
            sds_id              INTEGER,
            notes               TEXT,
            created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


init_inventory_db()


@app.route("/inventory")
def inventory():
    search_q   = request.args.get("q", "").strip()
    flash_msg  = request.args.get("msg", "")
    flash_type = request.args.get("msg_type", "success")

    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if search_q:
        cursor.execute("""
            SELECT id, name, location, quantity, unit, low_stock_threshold, sds_id, notes
            FROM chemical_inventory
            WHERE name LIKE ? OR location LIKE ? OR notes LIKE ?
            ORDER BY name
        """, (f"%{search_q}%",) * 3)
    else:
        cursor.execute("""
            SELECT id, name, location, quantity, unit, low_stock_threshold, sds_id, notes
            FROM chemical_inventory ORDER BY name
        """)
    items = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM chemical_inventory")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT location) FROM chemical_inventory WHERE location IS NOT NULL AND location != ''")
    location_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM chemical_inventory
        WHERE low_stock_threshold IS NOT NULL AND quantity IS NOT NULL
          AND quantity <= low_stock_threshold
    """)
    low_stock_count = cursor.fetchone()[0]

    cursor.execute("SELECT DISTINCT location FROM chemical_inventory WHERE location IS NOT NULL AND location != '' ORDER BY location")
    locations = [r[0] for r in cursor.fetchall()]

    cursor.execute("SELECT id, file_name FROM sds ORDER BY file_name")
    sds_list = cursor.fetchall()

    conn.close()

    return render_template_string(
        INVENTORY_HTML,
        items=items,
        total=total,
        location_count=location_count,
        low_stock_count=low_stock_count,
        locations=locations,
        sds_list=sds_list,
        search_q=search_q,
        flash_msg=flash_msg,
        flash_type=flash_type,
    )


@app.route("/inventory/add", methods=["POST"])
def inventory_add():
    name      = request.form.get("name", "").strip()
    location  = request.form.get("location", "").strip() or None
    quantity  = request.form.get("quantity", "").strip() or None
    unit      = request.form.get("unit", "").strip() or None
    threshold = request.form.get("low_stock_threshold", "").strip() or None
    sds_id    = request.form.get("sds_id", "").strip() or None
    notes     = request.form.get("notes", "").strip() or None

    if not name:
        return redirect("/inventory?msg=Name+is+required&msg_type=error")

    try:
        qty_val = float(quantity) if quantity else None
        thr_val = float(threshold) if threshold else None
        sid_val = int(sds_id) if sds_id else None
    except ValueError:
        return redirect("/inventory?msg=Invalid+number+value&msg_type=error")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO chemical_inventory (name, location, quantity, unit, low_stock_threshold, sds_id, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, location, qty_val, unit, thr_val, sid_val, notes))
    conn.commit()
    conn.close()

    from urllib.parse import quote
    return redirect(f"/inventory?msg={quote(name + ' added successfully')}&msg_type=success")


@app.route("/inventory/edit/<int:item_id>", methods=["POST"])
def inventory_edit(item_id):
    name      = request.form.get("name", "").strip()
    location  = request.form.get("location", "").strip() or None
    quantity  = request.form.get("quantity", "").strip() or None
    unit      = request.form.get("unit", "").strip() or None
    threshold = request.form.get("low_stock_threshold", "").strip() or None
    sds_id    = request.form.get("sds_id", "").strip() or None
    notes     = request.form.get("notes", "").strip() or None

    if not name:
        return redirect("/inventory?msg=Name+is+required&msg_type=error")

    try:
        qty_val = float(quantity) if quantity else None
        thr_val = float(threshold) if threshold else None
        sid_val = int(sds_id) if sds_id else None
    except ValueError:
        return redirect("/inventory?msg=Invalid+number+value&msg_type=error")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        UPDATE chemical_inventory
        SET name=?, location=?, quantity=?, unit=?, low_stock_threshold=?, sds_id=?, notes=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (name, location, qty_val, unit, thr_val, sid_val, notes, item_id))
    conn.commit()
    conn.close()

    from urllib.parse import quote
    return redirect(f"/inventory?msg={quote(name + ' updated')}&msg_type=success")


@app.route("/inventory/delete/<int:item_id>", methods=["POST"])
def inventory_delete(item_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM chemical_inventory WHERE id=?", (item_id,))
    row = cursor.fetchone()
    if row:
        conn.execute("DELETE FROM chemical_inventory WHERE id=?", (item_id,))
        conn.commit()
    conn.close()

    name = row[0] if row else "Item"
    from urllib.parse import quote
    return redirect(f"/inventory?msg={quote(name + ' deleted')}&msg_type=success")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
