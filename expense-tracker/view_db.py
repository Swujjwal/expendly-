"""Helper script to inspect the contents of spendly.db in the terminal."""

import os
import sys
from database.db import get_db, DB_PATH

def main():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at: {DB_PATH}")
        sys.exit(1)

    conn = get_db()
    print("=" * 70)
    print(f"DATABASE: {os.path.basename(DB_PATH)}")
    print(f"LOCATION: {DB_PATH}")
    print("=" * 70)

    # Tables
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';").fetchall()]
    
    for table in tables:
        print(f"\nTABLE: {table}")
        print("-" * 70)
        rows = conn.execute(f"SELECT * FROM {table};").fetchall()
        if not rows:
            print("  (empty table)")
            continue
        
        # Get column names
        cols = rows[0].keys()
        # Print header
        header = " | ".join(f"{col:<15}" for col in cols)
        print(header)
        print("-" * len(header))
        # Print rows
        for row in rows:
            line = []
            for col in cols:
                val = str(row[col])
                if len(val) > 20 and col == "password_hash":
                    val = val[:15] + "..."
                elif len(val) > 25:
                    val = val[:22] + "..."
                line.append(f"{val:<15}")
            print(" | ".join(line))

    conn.close()
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()

