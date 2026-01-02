import sys
import sqlite3

# Database schema mapping:
STATUS_UNWATCHED = 0
STATUS_SKIPPED = 1
STATUS_WATCHED = 2


def get_connection(db_path="pm.db"):
    """Create and return SQLite connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row # you can then call random_movie['title']
    return conn


def select_random(cursor):
    """Return a random unwatched movie or None.
    """
    cursor.execute("""
        SELECT *
        FROM films
        WHERE status = ?
        ORDER BY RANDOM()
        LIMIT 1;
    """, (STATUS_UNWATCHED,))

    return cursor.fetchone()


def list_unwatched(cursor):
    """Displays unwatched movies"""

    cursor.execute("""
        SELECT *
        FROM films
        WHERE status = ?
        ORDER BY year;
    """, (STATUS_UNWATCHED,))
    return cursor.fetchall()


def list_watched(cursor):
    """Displays all watched movies"""
    cursor.execute("""
        SELECT *
        FROM films
        WHERE status = ?
        ORDER BY year;
    """, (STATUS_WATCHED,))
    return cursor.fetchall()

def show_help():
    """Display available commands"""
    with open('help.txt', 'r', encoding="utf-8") as file:
        print(file.read())

def vote_on_movie():
    pass

# Main program - handle command-line arguments
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: No command provided. Use --help for usage information.")
        sys.exit(1)

    command = sys.argv[1].lower()
# initiate connection with db
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if command == "randommovie":
            movie = select_random(cursor)

            if movie is None: # for when you run out of movies
                print("""
You've watched all the movies!
Update your database with new movies for future date nights.
""")
            else:
                print(f"Tonight's choice is {movie['title']} ({movie['year']})")
                print("Now vote on it:")

        elif command == "listunwatched":
            unwatched_movies = list_unwatched(cursor)
            if not unwatched_movies:
                print("No unwatched movies found.")
            else:
                print("Here are your unwatched movies:")
                print()
                for film in unwatched_movies:
                    print(f"{film['id']}| {film['title']} ({film['year']})")

        elif command == "listwatched":
            watched_movies = list_watched(cursor)
            if not watched_movies:
                print("No watched movies found.")
            else:
                print("Here are your watched movies:")
                print()
                for film in watched_movies:
                    print(f"{film['id']}| {film['title']} ({film['year']})")            

        elif command == "--help":
            show_help()

        else:
            print(f"Error: Unknown command '{command}'")
            sys.exit(1)

    finally:
        conn.close()
