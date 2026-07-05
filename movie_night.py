import argparse
import csv
import os
import sqlite3
from pathlib import Path

# Database schema mapping
STATUS_UNWATCHED = 0
STATUS_SKIPPED = 1
STATUS_WATCHED = 2

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = PROJECT_DIR / "pm.db"
HELP_PATH = PROJECT_DIR / "help.txt"
DEFAULT_SEED_PATH = PROJECT_DIR / "data" / "seed-movies.csv"
REQUIRED_SEED_HEADERS = ("id", "title", "year", "director")


def resolve_db_path(db_path=None):
    """Return the configured SQLite database path."""
    if db_path is not None:
        return Path(db_path)
    return Path(os.environ.get("MOVIE_NIGHT_DB_PATH", DEFAULT_DB_PATH))


def get_connection(db_path=None):
    """Create and return SQLite connection."""
    conn = sqlite3.connect(resolve_db_path(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_films_table(conn):
    """Create the films table if needed."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS films (
            id INTEGER PRIMARY KEY,
            title TEXT,
            year INTEGER,
            status INTEGER NOT NULL DEFAULT 0 CHECK (status IN (0, 1, 2)),
            director TEXT,
            rewatch_worthy INTEGER DEFAULT NULL
                CHECK (rewatch_worthy IN (0, 1) OR rewatch_worthy IS NULL)
        );
        """
    )
    conn.commit()


def has_table(conn, table_name):
    """Return True if a SQLite table exists."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?;",
        (table_name,),
    ).fetchone()
    return row is not None


def read_seed_movies(seed_path=DEFAULT_SEED_PATH):
    """Read movie seed rows from CSV and validate the expected headers."""
    with Path(seed_path).open(newline="", encoding="utf-8") as seed_file:
        reader = csv.DictReader(seed_file)
        if reader.fieldnames != list(REQUIRED_SEED_HEADERS):
            expected = ", ".join(REQUIRED_SEED_HEADERS)
            actual = ", ".join(reader.fieldnames or ())
            raise ValueError(f"Seed CSV must have headers: {expected}. Found: {actual}")

        movies = []
        for line_number, row in enumerate(reader, start=2):
            try:
                movie_id = int(row["id"])
                year = int(row["year"])
            except ValueError as exc:
                raise ValueError(
                    f"Seed CSV line {line_number} has a non-numeric id or year."
                ) from exc

            title = row["title"].strip()
            director = row["director"].strip()
            if not title:
                raise ValueError(f"Seed CSV line {line_number} has an empty title.")

            movies.append((movie_id, title, year, director))

    if not movies:
        raise ValueError("Seed CSV does not contain any movies.")

    return movies


def create_database_from_csv(db_path=DEFAULT_DB_PATH, seed_path=DEFAULT_SEED_PATH):
    """Create or replace the films table contents from a seed CSV."""
    conn = get_connection(db_path)
    try:
        ensure_films_table(conn)
        ensure_voters_table(conn)
        movies = read_seed_movies(seed_path)

        with conn:
            conn.execute("DELETE FROM films;")
            conn.executemany(
                """
                INSERT INTO films (id, title, year, director, status, rewatch_worthy)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                [
                    (movie_id, title, year, director, STATUS_UNWATCHED, None)
                    for movie_id, title, year, director in movies
                ],
            )
        return len(movies)
    finally:
        conn.close()


def display_seed_path(seed_path):
    """Return a readable seed path for setup messages."""
    seed_path = Path(seed_path)
    try:
        return seed_path.relative_to(PROJECT_DIR)
    except ValueError:
        return seed_path


def ensure_database_ready(conn, seed_path=DEFAULT_SEED_PATH):
    """Offer to create the movie database from the seed CSV on first run."""
    if has_table(conn, "films"):
        return True

    print("No movie database was found.")
    print(
        f"You can edit {display_seed_path(seed_path)} first, or replace it "
        f"with your own CSV using these headers: {', '.join(REQUIRED_SEED_HEADERS)}."
    )
    if not ask_yes_no(f"Create {DEFAULT_DB_PATH.name} from the seed CSV now? (Y/N): "):
        print("Database setup skipped. Create a database before running movie commands.")
        return False

    ensure_films_table(conn)
    ensure_voters_table(conn)
    movies = read_seed_movies(seed_path)
    with conn:
        conn.executemany(
            """
            INSERT INTO films (id, title, year, director, status, rewatch_worthy)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            [
                (movie_id, title, year, director, STATUS_UNWATCHED, 0)
                for movie_id, title, year, director in movies
            ],
        )
    print(f"Created {DEFAULT_DB_PATH.name} with {len(movies)} movies.")
    return True


def ensure_voters_table(conn):
    """Create the persistent voter-name configuration table if needed."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS voters (
            position INTEGER PRIMARY KEY CHECK (position IN (1, 2)),
            name TEXT NOT NULL COLLATE NOCASE UNIQUE
                CHECK (length(trim(name)) > 0)
        );
        """
    )
    conn.commit()


def load_voters(conn):
    """Return saved voter names in voting order."""
    rows = conn.execute(
        "SELECT name FROM voters ORDER BY position;"
    ).fetchall()
    return [row["name"] for row in rows]


def ask_voter_name(prompt, existing_names=()):
    """Prompt until a non-empty, unique voter name is entered."""
    existing = {name.casefold() for name in existing_names}

    while True:
        name = input(prompt).strip()
        if not name:
            print("Name cannot be empty.")
        elif name.casefold() in existing:
            print("Voter names must be different.")
        else:
            return name


def get_or_create_voters(conn):
    """Load two voter names or perform first-run setup and persist them."""
    ensure_voters_table(conn)
    voters = load_voters(conn)
    if len(voters) == 2:
        return voters

    print("Welcome! Let's set up the two voters.")
    first_name = ask_voter_name("Enter voter 1's name: ")
    second_name = ask_voter_name(
        "Enter voter 2's name: ", existing_names=(first_name,)
    )

    with conn:
        conn.execute("DELETE FROM voters;")
        conn.executemany(
            "INSERT INTO voters (position, name) VALUES (?, ?);",
            ((1, first_name), (2, second_name)),
        )

    print(f"Voters saved: {first_name} and {second_name}.")
    return [first_name, second_name]


def update_movie_status(cursor, movie_id, status):
    """Update the status of a movie."""

    cursor.execute(
        """
        UPDATE films
        SET status = ?
        WHERE id = ?;
        """,
        (status, movie_id),
    )


def select_random(cursor):
    """Return a random unwatched movie or None."""
    cursor.execute(
        """
        SELECT *
        FROM films
        WHERE status = ?
        ORDER BY RANDOM()
        LIMIT 1;
        """,
        (STATUS_UNWATCHED,),
    )
    return cursor.fetchone()


def list_unwatched(cursor):
    """Return all unwatched movies."""
    cursor.execute(
        """
        SELECT *
        FROM films
        WHERE status = ?
        ORDER BY year;
        """,
        (STATUS_UNWATCHED,),
    )
    return cursor.fetchall()


def list_watched(cursor):
    """Return all watched movies."""
    cursor.execute(
        """
        SELECT *
        FROM films
        WHERE status = ?
        ORDER BY year;
        """,
        (STATUS_WATCHED,),
    )
    return cursor.fetchall()


def show_help():
    """Display available commands."""
    print(HELP_PATH.read_text(encoding="utf-8"))


def ask_yes_no(prompt):
    """Prompt user for Y/N input and return True/False."""
    while True:
        response = input(prompt).strip().lower()
        if response == "y":
            return True
        if response == "n":
            return False
        print("Invalid response! Please enter Y/N.")


def vote_on_movie(cursor, conn, voters):
    """Handle random movie selection and voting loop."""
    while True:
        movie = select_random(cursor)

        if movie is None:
            print("You've cleared all the movies!")
            print("Time to update your database file.")
            return

        print(f"Tonight's choice is {movie['title']} ({movie['year']})")
        print("Now it's time to vote!")

        first_vote = ask_yes_no(
            f"{voters[0]}, do you want to watch {movie['title']} ({movie['year']})? (Y/N): "
        )
        second_vote = ask_yes_no(
            f"{voters[1]}, do you want to watch {movie['title']} ({movie['year']})? (Y/N): "
        )

        if first_vote or second_vote:
            print(f"{movie['title']} ({movie['year']}) was selected.")
            print("It will be marked as Watched automatically.")
            update_movie_status(cursor, movie["id"], STATUS_WATCHED)
            conn.commit()
            return
        else:
            print(f"{movie['title']} ({movie['year']}) was REJECTED.")
            print("It will be marked as Skipped automatically.")
            update_movie_status(cursor, movie["id"], STATUS_SKIPPED)
            conn.commit()

            if not ask_yes_no("Do you want to try finding another random movie? (Y/N): "):
                print("Good bye!")
                return


def build_parser():
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Select and track movies for movie night.",
        epilog=HELP_PATH.read_text(encoding="utf-8"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=("randommovie", "listunwatched", "listwatched"),
        help="operation to perform",
    )
    return parser


def main(argv=None, db_path=None):
    """Run the command-line application."""
    args = build_parser().parse_args(argv)
    conn = get_connection(resolve_db_path(db_path))

    try:
        if not ensure_database_ready(conn):
            return 1

        cursor = conn.cursor()

        if args.command == "randommovie":
            voters = get_or_create_voters(conn)
            vote_on_movie(cursor, conn, voters)

        elif args.command == "listunwatched":
            movies = list_unwatched(cursor)
            if not movies:
                print("No unwatched movies found.")
            else:
                print("Here are your unwatched movies:\n")
                for film in movies:
                    print(f"{film['id']} | {film['title']} ({film['year']})")

        elif args.command == "listwatched":
            movies = list_watched(cursor)
            if not movies:
                print("No watched movies found.")
            else:
                print("Here are your watched movies:\n")
                for film in movies:
                    print(f"{film['id']} | {film['title']} ({film['year']})")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
