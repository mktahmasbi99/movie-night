import csv
import re

INPUT_FILE = "movie-list.txt"
OUTPUT_FILE = "movie-list.csv"

# Regex pattern:
# 1. Title — 1902
pattern = re.compile(
    r"""
    ^\s*
    (?P<id>\d+)
    \.\s+
    (?P<title>.+?)
    \s+—\s+
    (?P<year>\d{4})
    \s*$
    """,
    re.VERBOSE
)

rows = []

with open(INPUT_FILE, "r", encoding="utf-8") as infile:
    for line_number, line in enumerate(infile, start=1):
        line = line.strip()

        if not line:
            continue  # skip empty lines

        match = pattern.match(line)
        if not match:
            print(f"Warning: line {line_number} skipped (unrecognized format)")
            continue

        rows.append({
            "id": int(match.group("id")),
            "title": match.group("title").strip(),
            "year": int(match.group("year"))
        })

# Write CSV
with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as outfile:
    writer = csv.DictWriter(outfile, fieldnames=["id", "title", "year"])
    writer.writeheader()
    writer.writerows(rows)

print(f"Successfully wrote {len(rows)} films to '{OUTPUT_FILE}'")