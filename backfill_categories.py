"""
backfill_categories.py
----------------------
Classifies existing SDS records into product categories using
keyword rules — no API key or external service required.

Run after your sds.db is populated:
    python backfill_categories.py

Options:
    --dry-run        Print classifications without writing to DB
    --reset          Clear all categories and re-classify everything
    --limit N        Only process first N records (good for testing)
    --uncategorized  List all records that landed in "Uncategorized"
"""

import sqlite3
import re
import os
import sys
import argparse

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "sds.db")

CONTENT_SNIPPET_LEN = 400

# ── Category rules ────────────────────────────────────────────────────────────
#
# Each entry: (category_name, [keywords...])
# Rules are tried IN ORDER — first match wins.
# Keywords matched case-insensitively against filename first, then content snippet.
# More specific rules should come BEFORE more general ones.

CATEGORY_RULES: list[tuple[str, list[str]]] = [

    # ── Automotive fluids ─────────────────────────────────────────────────────
    ("Motor Oils",          ["motor oil", "engine oil", "5w-", "5w30", "5w20", "0w-", "10w-",
                             "10w30", "10w40", "15w-", "synthetic oil", "gtx", "pennzoil",
                             "mobil 1", "valvoline", "quaker state", "delo", "rotella",
                             "2 cycle oil", "two cycle oil", "bar and chain oil",
                             "chain oil", "compressor oil", "defrix oil", "marvel lubricating",
                             "pump armor"]),

    ("Transmission Fluids", ["transmission fluid", "atf ", "atf+", "dexron", "mercon",
                              "cvt fluid", "power steering fluid", "power steer"]),

    ("Brake Fluids",        ["brake fluid", "dot 3", "dot 4", "dot 5", "dot3", "dot4", "dot5",
                              "hydraulic brake"]),

    ("Antifreeze & Coolants", ["antifreeze", "anti-freeze", "coolant", "cool guard",
                                "dex-cool", "ethylene glycol", "propylene glycol",
                                "radiator fluid", "peak", "zerex", "prestone"]),

    ("Hydraulic Fluids",    ["hydraulic fluid", "hydraulic oil", "jack oil", "lift fluid",
                              "hyd fluid", "hyd oil"]),

    ("Differential & Gear Oils", ["gear oil", "gear lube", "differential fluid", "diff fluid",
                                   "75w-", "75w90", "80w-", "80w90", "gl-4", "gl-5",
                                   "limited slip"]),

    ("Refrigerants",        ["refrigerant", "r-134", "r134", "r-1234", "r1234", "freon",
                              "a/c refrigerant", "ac refrigerant", "hvac refrigerant"]),

    # ── Fuels & propellants ───────────────────────────────────────────────────
    ("Fuels",               ["gasoline", "diesel fuel", "fuel additive", "fuel system",
                              "octane booster", "starting fluid", "ether start",
                              "kerosene", "petroleum naphtha", "propane", "butane",
                              "lifestyle propane", "bernzomatic", "mag-torch",
                              "fuel stabilizer"]),

    # ── Gases ─────────────────────────────────────────────────────────────────
    ("Welding Gases",       ["welding gas", "argon", "carbon dioxide welding", "co2 welding",
                              "shielding gas", "mig gas", "tig gas", "acetylene",
                              "welding wire", "anti spatter", "weld spatter", "whale spray"]),

    ("Compressed Gases",    ["compressed gas", "nitrogen", "helium", "co2 cartridge",
                              "carbon dioxide", "oxygen cylinder", "compressed air",
                              "aerosol propellant", "oxygen.pdf"]),

    # ── Lubricants & greases ──────────────────────────────────────────────────
    ("Greases",             ["grease", "chassis lube", "wheel bearing", "bearing lube",
                              "moly", "lithium grease", "white grease", "nlgi"]),

    ("Lubricants",          ["lubricant", "lube", "wd-40", "wd40", "penetrant",
                              "multi-purpose lube", "spray lube", "chain lube",
                              "silicone lube", "ptfe", "teflon lube", "dry lube",
                              "anti-seize", "anti seize", "thread lube", "clp liquid",
                              "break-free", "cutting fluid", "rapid tap", "ez break",
                              "nickel grade"]),

    # ── Cleaning & stripping ──────────────────────────────────────────────────
    ("Degreasers",          ["degreaser", "degreasing", "parts cleaner", "brake cleaner",
                              "carburetor cleaner", "carb cleaner", "throttle body cleaner",
                              "intake cleaner", "engine degreaser", "solvent cleaner",
                              "mass air flow", "maf cleaner", "electronic cleaner",
                              "qd electronic", "maintenance cleaner", "mutoh",
                              "rapid tac", "goof off", "ink remover", "cured ink"]),

    ("Strippers & Removers", ["stripper", "stripping", "stripoxy", "citristrip",
                               "paint stripper", "paint remover", "graffiti remover",
                               "adhesive remover", "label remover"]),

    ("Glass Cleaners",      ["glass cleaner", "windshield cleaner", "window cleaner",
                              "glass wash", "rain-x", "rainx", "windshield washer",
                              "washer fluid", "windshield fluid"]),

    ("Mechanical Cleaners", ["hand cleaner", "hand soap", "hand wash", "shop soap",
                              "gojo", "mechanic soap", "waterless cleaner", "fast orange",
                              "orange clean"]),

    ("Carpet & Fabric Cleaners", ["carpet cleaner", "rug cleaner", "fabric cleaner",
                                   "upholstery cleaner", "scotchgard", "hoover"]),

    ("Soaps & Cleaners",    ["soap", "detergent", "all-purpose cleaner", "surface cleaner",
                              "disinfectant", "sanitizer", "floor cleaner", "fabuloso",
                              "lysol", "toilet bowl", "mold cleaner", "slide mold"]),

    # ── Protective & specialty coatings ───────────────────────────────────────
    ("Paints & Solvents",   ["paint", "primer", "enamel", "lacquer", "solvent",
                              "thinner", "reducer", "acetone", "xylene", "toluene",
                              "mineral spirits", "naphtha", "voc", "behr", "color sample",
                              "denatured alcohol", "muriatic acid", "klean strip",
                              "sunnyside"]),

    ("Protective Coatings", ["protectant", "protective coating", "armor all", "303 aerospace",
                              "plasti dip", "plastidip", "flex seal", "durabak",
                              "polyurethane coating", "scotchgard", "heat barrier",
                              "goss heat", "desiccant", "silica gel"]),

    ("Rust Inhibitors",     ["rust", "rustproofing", "rust-oleum", "rustoleum",
                              "corrosion inhibitor", "rust inhibitor", "rust preventive",
                              "cavity wax", "undercoat", "surfox", "passivation",
                              "walter surfox", "copper sulfate"]),

    ("Polishes & Waxes",    ["polish", "wax", "detailer", "car wax", "carnauba",
                              "paint sealant", "clear coat", "buffing compound",
                              "rubbing compound", "swirl remover", "meguiar", "turtle wax",
                              "mothers", "chemical guys", "raytech compound"]),

    # ── Adhesives & sealants ──────────────────────────────────────────────────
    ("Adhesives & Sealants", ["adhesive", "sealant", "rtv", "silicone sealant",
                               "gasket maker", "gasket sealer", "thread sealant",
                               "threadlock", "thread lock", "loctite", "permatex",
                               "epoxy", "super glue", "cyanoacrylate", "3m adhesive",
                               "trim adhesive", "weather strip", "contact cement",
                               "weldwood", "aquaseal", "e-6000", "titebond", "wood glue",
                               "pvc cement", "pipe cement", "oatey", "harvey pipe",
                               "pipe thread", "leak lock", "thread compound",
                               "bondo", "body filler", "filler"]),

    # ── Aerosols ──────────────────────────────────────────────────────────────
    ("Aerosols",            ["aerosol", "spray can", "spray paint", "touch-up spray",
                              "pressurized spray"]),

    # ── Batteries ─────────────────────────────────────────────────────────────
    ("Battery Products",    ["battery", "lead acid", "electrolyte", "battery terminal",
                              "battery cleaner", "battery protector", "12v battery"]),

    # ── 3D printing materials ─────────────────────────────────────────────────
    ("3D Printing Materials", ["bambu", "pla", "petg", "abs-gf", "tpu", "filament",
                                "resin", "liqcreate", "3d print", "fdm", "support for pla"]),

    # ── Pest control ──────────────────────────────────────────────────────────
    ("Pest Control",        ["insecticide", "pesticide", "herbicide", "bug stop", "roach",
                              "wasp", "hornet", "ant killer", "rat killer", "mouse killer",
                              "spectracide", "combat roach", "terro", "tomcat",
                              "weed killer", "grass killer"]),

    # ── Leather & interior ────────────────────────────────────────────────────
    ("Leather & Trim Care", ["leather cleaner", "leather conditioner", "leather care",
                              "leather protect", "vinyl cleaner", "interior cleaner"]),

    # ── First aid & safety ────────────────────────────────────────────────────
    ("Antiseptics",         ["antiseptic", "isopropyl alcohol", "rubbing alcohol",
                              "hand sanitizer", "first aid", "hydrogen peroxide"]),

    # ── Misc shop supplies ────────────────────────────────────────────────────
    ("Deodorizers",         ["deodorizer", "odor", "odour", "air freshener", "ozium",
                              "odor eliminator"]),

    ("Ice Melt",            ["ice melt", "de-icer", "deicer", "windshield de-icer",
                              "lock de-icer", "freeze guard"]),

    ("Shop Supplies",       ["rag", "absorbent", "oil dry", "shop towel", "safety solvent",
                              "mineral oil", "spif", "s.p.i.f"]),
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def classify(file_name: str, content: str) -> str:
    name_lower    = file_name.lower().replace("_", " ").replace("-", " ")
    snippet_lower = (content or "")[:CONTENT_SNIPPET_LEN].lower()

    for category, keywords in CATEGORY_RULES:
        for kw in keywords:
            pattern = re.escape(kw)
            if re.search(pattern, name_lower):
                return category
            if re.search(pattern, snippet_lower):
                return category

    return "Uncategorized"


def init_schema(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)
    existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(sds)")}
    if "category_id" not in existing_cols:
        cursor.execute("ALTER TABLE sds ADD COLUMN category_id INTEGER REFERENCES categories(id)")
        print("  + Added category_id to sds")
    if "category_raw" not in existing_cols:
        cursor.execute("ALTER TABLE sds ADD COLUMN category_raw TEXT")
        print("  + Added category_raw to sds")
    if "manually_overridden" not in existing_cols:
        cursor.execute("ALTER TABLE sds ADD COLUMN manually_overridden INTEGER DEFAULT 0")
        print("  + Added manually_overridden to sds")
    conn.commit()


def reset_categories(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    # Only clear records the admin panel hasn't manually corrected.
    cursor.execute(
        "UPDATE sds SET category_id = NULL, category_raw = NULL "
        "WHERE manually_overridden = 0 OR manually_overridden IS NULL"
    )
    # Keep any category still in use by a manually-overridden record.
    cursor.execute("""
        DELETE FROM categories
        WHERE id NOT IN (
            SELECT category_id FROM sds
            WHERE category_id IS NOT NULL AND manually_overridden = 1
        )
    """)
    conn.commit()
    print("  + Cleared category data for non-overridden records")


def get_or_create_category(conn: sqlite3.Connection, name: str) -> int:
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM categories WHERE name = ?", (name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("INSERT INTO categories (name) VALUES (?)", (name,))
    conn.commit()
    return cursor.lastrowid


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill SDS categories (rule-based, no API key)")
    parser.add_argument("--dry-run",       action="store_true")
    parser.add_argument("--reset",         action="store_true")
    parser.add_argument("--limit",         type=int, default=None)
    parser.add_argument("--uncategorized", action="store_true")
    args = parser.parse_args()

    print(f"\n-- SDS Category Backfill {'(DRY RUN) ' if args.dry_run else ''}--")
    print(f"   DB: {DB_PATH}")

    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\nInitialising schema...")
    init_schema(conn)

    if args.reset and not args.dry_run:
        print("Resetting existing categories...")
        reset_categories(conn)

    if args.reset:
        query = (
            "SELECT id, file_name, content FROM sds "
            "WHERE manually_overridden = 0 OR manually_overridden IS NULL "
            "ORDER BY file_name"
        )
    else:
        query = (
            "SELECT id, file_name, content FROM sds "
            "WHERE category_id IS NULL "
            "AND (manually_overridden = 0 OR manually_overridden IS NULL) "
            "ORDER BY file_name"
        )
    if args.limit:
        query += f" LIMIT {args.limit}"

    cursor.execute(query)
    rows = cursor.fetchall()

    if not rows:
        print("\nNothing to classify. Use --reset to re-classify everything.")
        conn.close()
        return

    total = len(rows)
    print(f"\nClassifying {total} record(s)...\n")

    category_counts: dict[str, int] = {}
    uncategorized_files: list[str]  = []

    for i, (sds_id, file_name, content) in enumerate(rows, start=1):
        category = classify(file_name, content)
        category_counts[category] = category_counts.get(category, 0) + 1
        if category == "Uncategorized":
            uncategorized_files.append(file_name)

        flag = "!!" if category == "Uncategorized" else "  "
        print(f"[{i:>4}/{total}] {flag} {file_name:<60}  ->  {category}")

        if not args.dry_run:
            cat_id = get_or_create_category(conn, category)
            # Rows reaching here are already guaranteed non-overridden by the
            # query above, so it's always safe to also update the display
            # column directly instead of relying on a separate sync step.
            cursor.execute(
                "UPDATE sds SET category_id = ?, category_raw = ?, category = ? "
                "WHERE id = ? AND (manually_overridden = 0 OR manually_overridden IS NULL)",
                (cat_id, category, category, sds_id)
            )
            conn.commit()

    conn.close()

    print(f"\n-- Summary {'(DRY RUN) ' if args.dry_run else ''}--")
    print(f"Classified: {total}/{total}  |  Categories: {len(category_counts)}\n")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        bar = "#" * min(count, 50)
        print(f"  {count:>4}  {cat:<35}  {bar}")

    if uncategorized_files:
        pct = len(uncategorized_files) / total * 100
        print(f"\n!! {len(uncategorized_files)} records are Uncategorized ({pct:.1f}%)")
        if args.uncategorized:
            print("   Add keywords for these files:")
            for f in uncategorized_files:
                print(f"   - {f}")
        else:
            print("   Re-run with --uncategorized to list them")

    if args.dry_run:
        print("\n[Dry run -- no changes written to DB]")
    else:
        print("\nDone. Next: add the admin UI to app.py.")


if __name__ == "__main__":
    main()