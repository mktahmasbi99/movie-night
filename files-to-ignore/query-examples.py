import sqlite3 # Imports sqlite

# Connects to database
conn = sqlite3.connect("pm.db")
cursor = conn.cursor()

# SQL query goes here:
cursor.execute("SELECT * FROM films;")

# Fetch results
films = cursor.fetchall()

# Print results
for film in films:
    print(film)

# close connection
conn.close()