import sqlite3
import csv
import os

CSV_FILE = "movie-list.csv"
DB_FILE = "pm.db"

# REMOVES EXISTING MOVIE DATABASE. USE WITH CARE. DEPRICATED.
if os.path.exists(DB_FILE):
    os.remove(DB_FILE)

# Connect to SQLite
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

# Create the films table
cursor.execute("""
CREATE TABLE films (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    year INTEGER NOT NULL,
    status INTEGER NOT NULL DEFAULT 0
)
""")

# status: 0 = not watched, 1 = skipped, 2 = watched

# Import CSV
with open(CSV_FILE, newline="", encoding="utf-8") as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        title = row["title"].strip()
        year = int(row["year"])
        cursor.execute(
            "INSERT INTO films (title, year) VALUES (?, ?)",
            (title, year)
        )

conn.commit()
conn.close()

print(f"Successfully imported '{CSV_FILE}' into '{DB_FILE}' with {sum(1 for _ in open(CSV_FILE))-1} films.")
