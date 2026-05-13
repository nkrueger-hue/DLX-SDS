"""
admin.py  ──  Drop-in admin blueprint for the DLX SDS Flask app.

Setup
─────
1.  pip install flask

2.  In app.py, add near the top:
        from admin import admin_bp
        app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-prod")
        app.register_blueprint(admin_bp)

3.  Set env vars before running:
        export ADMIN_PASSWORD=yourpassword
        export SECRET_KEY=a-long-random-string

4.  Run your migration once (or let the blueprint do it on first request):
        python -c "from admin import migrate; migrate()"

5.  Visit /admin  (login required).

Classifier integration
──────────────────────
Replace the stub `classify()` below with an import from your own module:
        from classifier import classify          # ← your function
The function must accept a content string and return a category string.
"""

import os
import sqlite3
import functools
from flask import (
    Blueprint, flash, redirect, render_template_string,
    request, session, url_for,
)

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(BASE_DIR, "sds.db")
ADMIN_PASS  = os.environ.get("ADMIN_PASSWORD", "admin")   # override via env

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# ── Classifier stub ───────────────────────────────────────────────────────────
# Replace this with `from classifier import classify` once you have the module.

# With this:
from backfill_categories import classify as _bc_classify

def classify(content: str, file_name: str = "") -> str:
    return _bc_classify(file_name, content)

def get_known_categories(conn) -> list[str]:
    """Pull live category list from the categories table, falling back to column values."""
    try:
        rows = conn.execute("SELECT name FROM categories ORDER BY name").fetchall()
        if rows:
            return ["Uncategorized"] + [r["name"] for r in rows if r["name"] != "Uncategorized"]
    except Exception:
        pass
    # Fallback: distinct values already in the category column
    rows = conn.execute(
        "SELECT DISTINCT category FROM sds WHERE category IS NOT NULL ORDER BY category"
    ).fetchall()
    return [r["category"] for r in rows] or ["Uncategorized"]


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def migrate():
    """Add admin columns to sds table if they don't exist."""
    conn = get_db()
    cur = conn.cursor()
    existing = {row[1] for row in cur.execute("PRAGMA table_info(sds)")}
    if "category" not in existing:
        cur.execute("ALTER TABLE sds ADD COLUMN category TEXT DEFAULT 'Uncategorized'")
    if "manually_overridden" not in existing:
        cur.execute("ALTER TABLE sds ADD COLUMN manually_overridden INTEGER DEFAULT 0")
    cur.execute("""
                UPDATE sds
                SET category = category_raw
                WHERE category_raw IS NOT NULL
                AND (category IS NULL OR category = 'Uncategorized')
                """)
    conn.commit()
    conn.close()

# Run migration automatically when blueprint is loaded
migrate()

# ── Auth ──────────────────────────────────────────────────────────────────────

def login_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin.login", next=request.path))
        return f(*args, **kwargs)
    return wrapper

# ── Templates ─────────────────────────────────────────────────────────────────

_BASE_CSS = """
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,400;0,500;0,600;1,400&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
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
    --green:    #2a6b3c;
    --green-l:  #3d9b59;
    --amber:    #7a5c1e;
    --amber-l:  #c49a30;
}
body { font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }

/* Header */
header {
    background: var(--red); padding: 0 24px;
    display: flex; align-items: center; justify-content: space-between;
    height: 56px; position: sticky; top: 0; z-index: 100;
    box-shadow: 0 2px 12px rgba(0,0,0,0.4);
}
header h1 { font-size: 15px; font-weight: 600; letter-spacing: 0.06em; color: white; text-transform: uppercase; }
.header-links { display: flex; gap: 16px; align-items: center; }
.header-links a { color: rgba(255,255,255,0.7); text-decoration: none; font-size: 13px; transition: color 0.15s; }
.header-links a:hover { color: white; }

/* Layout */
.wrap { max-width: 1100px; margin: 0 auto; padding: 28px 24px 64px; }

/* Flash messages */
.flash { padding: 10px 16px; border-radius: 6px; font-size: 13px; margin-bottom: 16px; }
.flash.success { background: var(--green); color: #b8f0c8; border: 1px solid var(--green-l); }
.flash.error   { background: #4a1a1a; color: #f0b8b8; border: 1px solid var(--red); }
.flash.info    { background: var(--amber); color: #f5e0a0; border: 1px solid var(--amber-l); }

/* Toolbar */
.toolbar {
    display: flex; align-items: center; flex-wrap: wrap; gap: 10px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 14px 16px; margin-bottom: 20px;
}
.toolbar form { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
select, input[type=text] {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 6px; color: var(--text); padding: 7px 12px;
    font-family: 'DM Sans', sans-serif; font-size: 13px; outline: none;
    transition: border-color 0.15s;
}
select:focus, input[type=text]:focus { border-color: var(--red); }
.ml-auto { margin-left: auto; }

/* Buttons */
.btn {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 8px 14px; border-radius: 6px; font-family: 'DM Sans', sans-serif;
    font-size: 13px; font-weight: 500; cursor: pointer; text-decoration: none;
    border: 1px solid transparent; transition: all 0.15s; white-space: nowrap;
}
.btn-primary   { background: var(--red);     color: white;        border-color: var(--red); }
.btn-primary:hover { background: var(--red-dark); border-color: var(--red-dark); }
.btn-ghost     { background: transparent; color: var(--muted);   border-color: var(--border); }
.btn-ghost:hover { color: var(--text); border-color: var(--muted); }
.btn-danger    { background: transparent; color: #e07070;         border-color: #6b3030; }
.btn-danger:hover { background: #4a1a1a; }
.btn-sm        { padding: 5px 10px; font-size: 12px; }
.btn-amber     { background: var(--amber); color: var(--amber-l); border-color: var(--amber); }
.btn-amber:hover { background: #5a4010; }
.btn[disabled] { opacity: 0.4; pointer-events: none; }

/* Stats bar */
.stats-bar {
    display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px;
}
.stat-chip {
    background: var(--card); border: 1px solid var(--border); border-radius: 8px;
    padding: 8px 14px; font-family: 'DM Mono', monospace; font-size: 12px;
    color: var(--muted); display: flex; align-items: center; gap: 6px;
}
.stat-chip strong { color: var(--text); font-size: 15px; }

/* Table */
.table-wrap { background: var(--card); border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
table { width: 100%; border-collapse: collapse; }
thead { background: var(--surface); }
th {
    padding: 11px 14px; text-align: left; font-size: 11px; font-weight: 600;
    letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted);
    border-bottom: 1px solid var(--border);
}
td { padding: 11px 14px; font-size: 13px; border-bottom: 1px solid var(--border); vertical-align: middle; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: rgba(255,255,255,0.02); }

.td-name { font-weight: 500; color: var(--accent); max-width: 280px; }
.td-name span { display: block; font-size: 11px; color: var(--muted); font-weight: 400; margin-top: 2px; font-family: 'DM Mono', monospace; }
.td-actions { display: flex; gap: 6px; align-items: center; }

/* Category badge */
.cat-badge {
    display: inline-block; padding: 3px 9px; border-radius: 20px; font-size: 11px;
    font-weight: 500; letter-spacing: 0.03em; white-space: nowrap;
}
.cat-Flammable      { background: #4a2e10; color: #f0a050; }
.cat-Corrosive      { background: #1a2e40; color: #60b0e0; }
.cat-Toxic          { background: #2a1040; color: #c080f0; }
.cat-Oxidizing      { background: #3a2a10; color: #d0a030; }
.cat-Irritant       { background: #1a3a20; color: #60c080; }
.cat-Compressed-Gas { background: #1a2a3a; color: #50a0d0; }
.cat-Health-Hazard  { background: #3a1a2a; color: #e070a0; }
.cat-Environmental  { background: #1a3a2a; color: #50c090; }
.cat-Uncategorized  { background: var(--surface); color: var(--muted); }

.override-dot {
    display: inline-block; width: 6px; height: 6px; border-radius: 50%;
    background: var(--amber-l); margin-left: 6px; vertical-align: middle;
    title: "Manually overridden";
}

/* Edit form */
.edit-card {
    background: var(--card); border: 1px solid var(--border); border-radius: 10px;
    padding: 28px; max-width: 680px;
}
.edit-card h2 { font-size: 16px; font-weight: 600; color: var(--accent); margin-bottom: 6px; }
.edit-card .sub { font-size: 12px; color: var(--muted); margin-bottom: 24px; font-family: 'DM Mono', monospace; }
.field { margin-bottom: 18px; }
.field label { display: block; font-size: 12px; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; color: var(--muted); margin-bottom: 6px; }
.field select, .field input[type=text] { width: 100%; padding: 10px 12px; }
.field textarea {
    width: 100%; background: var(--surface); border: 1px solid var(--border);
    border-radius: 6px; color: var(--text); padding: 10px 12px; resize: vertical;
    font-family: 'DM Mono', monospace; font-size: 12px; line-height: 1.6; outline: none;
    transition: border-color 0.15s;
}
.field textarea:focus { border-color: var(--red); }
.hint { font-size: 11px; color: var(--muted); margin-top: 5px; }
.form-actions { display: flex; gap: 10px; align-items: center; margin-top: 24px; padding-top: 20px; border-top: 1px solid var(--border); }

/* Login */
.login-wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center; }
.login-box {
    background: var(--card); border: 1px solid var(--border); border-radius: 12px;
    padding: 40px; width: 340px;
}
.login-box h2 { font-size: 18px; font-weight: 600; margin-bottom: 4px; }
.login-box p { font-size: 13px; color: var(--muted); margin-bottom: 28px; }
.login-box .field label { display: block; font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 6px; }
.login-box .field input { width: 100%; padding: 10px 12px; margin-bottom: 16px; }
.login-box .btn { width: 100%; justify-content: center; }
</style>
"""

LOGIN_HTML = """
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Admin Login – DLX SDS</title>
""" + _BASE_CSS + """
</head><body>
<div class="login-wrap">
  <div class="login-box">
    <h2>SDS Admin</h2>
    <p>Sign in to manage records.</p>
    {% for msg in msgs %}<div class="flash error">{{ msg }}</div>{% endfor %}
    <form method="POST">
      <div class="field">
        <label>Password</label>
        <input type="password" name="password" autofocus>
      </div>
      <button class="btn btn-primary" type="submit">Sign in</button>
    </form>
  </div>
</div>
</body></html>
"""

LIST_HTML = """
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Admin – DLX SDS</title>
""" + _BASE_CSS + """
</head><body>
<header>
  <h1>SDS Admin</h1>
  <div class="header-links">
    <a href="/">← Back to App</a>
    <a href="{{ url_for('admin.logout') }}">Logout</a>
  </div>
</header>
<div class="wrap">

  {% with messages = get_flashed_messages(with_categories=True) %}
    {% for cat, msg in messages %}
      <div class="flash {{ cat }}">{{ msg }}</div>
    {% endfor %}
  {% endwith %}

  <!-- Stats -->
  <div class="stats-bar">
    <div class="stat-chip"><strong>{{ total }}</strong> total records</div>
    <div class="stat-chip"><strong>{{ overridden }}</strong> manually set</div>
    <div class="stat-chip"><strong>{{ uncategorized }}</strong> uncategorized</div>
  </div>

  <!-- Toolbar -->
  <div class="toolbar">
    <form method="GET">
      <select name="category" onchange="this.form.submit()">
        <option value="">All categories</option>
        {% for cat in categories %}
          <option value="{{ cat }}" {% if selected_cat == cat %}selected{% endif %}>{{ cat }}</option>
        {% endfor %}
      </select>
      <input type="text" name="q" placeholder="Filter by name…" value="{{ q }}">
      <button class="btn btn-ghost" type="submit">Filter</button>
      {% if selected_cat or q %}
        <a class="btn btn-ghost" href="{{ url_for('admin.index') }}">Clear</a>
      {% endif %}
    </form>
    <div class="ml-auto">
      <form method="POST" action="{{ url_for('admin.reclassify_all') }}"
            onsubmit="return confirm('Reclassify all non-overridden records?')">
        <button class="btn btn-amber" type="submit">⟳ Reclassify All</button>
      </form>
    </div>
  </div>

  <!-- Table -->
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>ID</th>
          <th>Product Name</th>
          <th>Category</th>
          <th>Revision Date</th>
          <th>Hazard Codes</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {% if not rows %}
        <tr><td colspan="6" style="text-align:center;padding:40px;color:var(--muted);">No records found.</td></tr>
        {% endif %}
        {% for row in rows %}
        <tr>
          <td><span style="font-family:'DM Mono',monospace;font-size:11px;color:var(--muted);">#{{ row['id'] }}</span></td>
          <td class="td-name">
            {{ row['file_name'].replace('.pdf','').replace('.PDF','') }}
            <span>{{ row['file_name'] }}</span>
          </td>
          <td>
            {% set cat_class = (row['category'] or 'Uncategorized').replace(' ', '-') %}
            <span class="cat-badge cat-{{ cat_class }}">{{ row['category'] or 'Uncategorized' }}</span>
            {% if row['manually_overridden'] %}<span class="override-dot" title="Manually set"></span>{% endif %}
          </td>
          <td>
            {% if row['revision_date'] %}
              <span style="font-family:'DM Mono',monospace;font-size:12px;">{{ row['revision_date'] }}</span>
            {% else %}
              <span style="color:var(--muted);font-size:12px;">—</span>
            {% endif %}
          </td>
          <td style="font-family:'DM Mono',monospace;font-size:11px;color:var(--muted);max-width:160px;">
            {{ row['hazard_codes'] or '—' }}
          </td>
          <td>
            <div class="td-actions">
              <a class="btn btn-ghost btn-sm" href="{{ url_for('admin.edit', sds_id=row['id']) }}">Edit</a>
              <form method="POST" action="{{ url_for('admin.reclassify_one', sds_id=row['id']) }}" style="display:inline;">
                <button class="btn btn-ghost btn-sm" type="submit"
                  {% if row['manually_overridden'] %}title="Overridden – will reset"{% endif %}>
                  ⟳
                </button>
              </form>
            </div>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  <p style="margin-top:12px;font-size:11px;color:var(--muted);">
    Showing {{ rows|length }} of {{ total }} records.
    <span style="margin-left:12px;">● amber dot = manually overridden (skipped by Reclassify All)</span>
  </p>
</div>
</body></html>
"""

EDIT_HTML = """
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Edit #{{ row['id'] }} – Admin</title>
""" + _BASE_CSS + """
</head><body>
<header>
  <h1>SDS Admin</h1>
  <div class="header-links">
    <a href="{{ url_for('admin.index') }}">← Back to List</a>
    <a href="/">App</a>
    <a href="{{ url_for('admin.logout') }}">Logout</a>
  </div>
</header>
<div class="wrap">

  {% with messages = get_flashed_messages(with_categories=True) %}
    {% for cat, msg in messages %}
      <div class="flash {{ cat }}">{{ msg }}</div>
    {% endfor %}
  {% endwith %}

  <div class="edit-card">
    <h2>{{ row['file_name'].replace('.pdf','').replace('.PDF','') }}</h2>
    <div class="sub">ID #{{ row['id'] }} · {{ row['file_name'] }}</div>

    <form method="POST">

      <div class="field">
        <label>Category</label>
        <select name="category">
          {% for cat in categories %}
            <option value="{{ cat }}" {% if row['category'] == cat %}selected{% endif %}>{{ cat }}</option>
          {% endfor %}
        </select>
      </div>

      <div class="field">
        <label>Hazard Codes</label>
        <input type="text" name="hazard_codes" value="{{ row['hazard_codes'] or '' }}"
               placeholder="e.g. GHS02,GHS06">
        <div class="hint">Comma-separated GHS codes. Valid values: GHS01 – GHS09.</div>
      </div>

      <div class="field">
        <label>Revision Date</label>
        <input type="text" name="revision_date" value="{{ row['revision_date'] or '' }}"
               placeholder="e.g. 2024-03-15">
      </div>

      <div class="field">
        <label>Content Preview <span style="font-weight:400;text-transform:none;letter-spacing:0;">(editable)</span></label>
        <textarea name="content" rows="10">{{ row['content'] or '' }}</textarea>
        <div class="hint">Editing content will update what the classifier and search index see. Does not affect the PDF file.</div>
      </div>

      <div class="form-actions">
        <button class="btn btn-primary" type="submit">Save Changes</button>
        <a class="btn btn-ghost" href="{{ url_for('admin.index') }}">Cancel</a>
        <div class="ml-auto">
          <form method="POST" action="{{ url_for('admin.reclassify_one', sds_id=row['id']) }}" style="display:inline;">
            <button class="btn btn-ghost" type="submit">⟳ Re-run Classifier</button>
          </form>
        </div>
      </div>

    </form>
  </div>
</div>
</body></html>
"""

# ── Routes ────────────────────────────────────────────────────────────────────

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    msgs = []
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASS:
            session["admin_logged_in"] = True
            return redirect(request.args.get("next") or url_for("admin.index"))
        msgs.append("Incorrect password.")
    return render_template_string(LOGIN_HTML, msgs=msgs)


@admin_bp.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin.login"))


@admin_bp.route("/", methods=["GET"])
@login_required
def index():
    selected_cat = request.args.get("category", "")
    q            = request.args.get("q", "").strip()

    conn = get_db()
    cur  = conn.cursor()

    # Stats
    total        = cur.execute("SELECT COUNT(*) FROM sds").fetchone()[0]
    overridden   = cur.execute("SELECT COUNT(*) FROM sds WHERE manually_overridden = 1").fetchone()[0]
    uncategorized = cur.execute(
        "SELECT COUNT(*) FROM sds WHERE category IS NULL OR category = '' OR category = 'Uncategorized'"
    ).fetchone()[0]

    # Filtered query
    clauses, params = [], []
    if selected_cat:
        clauses.append("category = ?")
        params.append(selected_cat)
    if q:
        clauses.append("file_name LIKE ?")
        params.append(f"%{q}%")

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = cur.execute(
        f"SELECT id, file_name, content, revision_date, hazard_codes, category, manually_overridden "
        f"FROM sds {where} ORDER BY file_name",
        params,
    ).fetchall()
    categories=get_known_categories(conn),
    conn.close()

    return render_template_string(
        LIST_HTML,
        rows=rows,
        total=total,
        overridden=overridden,
        uncategorized=uncategorized,
        selected_cat=selected_cat,
        q=q,
    )


@admin_bp.route("/edit/<int:sds_id>", methods=["GET", "POST"])
@login_required
def edit(sds_id):
    conn = get_db()
    cur  = conn.cursor()

    if request.method == "POST":
        category      = request.form.get("category", "Uncategorized").strip()
        hazard_codes  = request.form.get("hazard_codes", "").strip()
        revision_date = request.form.get("revision_date", "").strip()
        content       = request.form.get("content", "").strip()

        cur.execute(
            """UPDATE sds
               SET category = ?, hazard_codes = ?, revision_date = ?,
                   content = ?, manually_overridden = 1
               WHERE id = ?""",
            (category, hazard_codes or None, revision_date or None, content, sds_id),
        )
        conn.commit()
        conn.close()
        flash("Record updated.", "success")
        return redirect(url_for("admin.index"))

    row = cur.execute(
        "SELECT id, file_name, content, revision_date, hazard_codes, category, manually_overridden "
        "FROM sds WHERE id = ?",
        (sds_id,),
    ).fetchone()
    categories=get_known_categories(conn),
    conn.close()

    if not row:
        flash("Record not found.", "error")
        return redirect(url_for("admin.index"))

    return render_template_string(
        EDIT_HTML,
        row=row,
    )


@admin_bp.route("/reclassify/<int:sds_id>", methods=["POST"])
@login_required
def reclassify_one(sds_id):
    conn = get_db()
    cur  = conn.cursor()
    row  = cur.execute("SELECT file_name, content FROM sds WHERE id = ?", (sds_id,)).fetchone()

    if row and row["content"]:
        new_cat = classify(row["content"], row["file_name"])
        cur.execute(
            "UPDATE sds SET category = ?, manually_overridden = 0 WHERE id = ?",
            (new_cat, sds_id),
        )
        conn.commit()
        flash(f"Record #{sds_id} reclassified as {new_cat}", "success")
    else:
        flash(f"Record #{sds_id} has no content to classify.", "error")

    conn.close()
    return redirect(request.referrer or url_for("admin.index"))


@admin_bp.route("/reclassify-all", methods=["POST"])
@login_required
def reclassify_all():
    conn = get_db()
    cur  = conn.cursor()
    rows = cur.execute(
        "SELECT id, file_name, content FROM sds WHERE manually_overridden = 0",
    ).fetchall()

    updated = 0
    for row in rows:
        if row["content"]:
            new_cat = classify(row["content"], row["file_name"])
            cur.execute("UPDATE sds SET category = ? WHERE id = ?", (new_cat, row["id"]))
            updated += 1

    conn.commit()
    conn.close()
    flash(f"Reclassified {updated} record(s). Manually overridden records were skipped.", "info")
    return redirect(url_for("admin.index"))