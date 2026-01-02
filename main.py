import sys
import sqlite3

# Database schema mapping:
STATUS_UNWATCHED = 0
STATUS_SKIPPED = 1
STATUS_WATCHED = 2

# Participants
VOTERS = ['Aikosh', 'Mo']

def get_connection(db_path="pm.db"):
    """Create and return SQLite connection."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row # you can then call random_movie['title']
    return conn


def select_random(cursor):
    """Return a random unwatched movie or None."""

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

def vote_on_movie(cursor):
    """Handle random movie selection and voting loop."""
    while True:
        movie_for_vote = select_random(cursor)
        #handle empty unwatched movies:
        if movie_for_vote is None:
            print("You've cleared all the movies!")
            print("Time to update your database file.")
            break
        print(f"Tonight's choice is {movie_for_vote['title']} ({movie_for_vote['year']})")
        print("Now it's time to vote!")

        ballot_box = {}
        for voter in VOTERS:
            while True:
                voter_response = input(f"{voter}, do you want to watch {movie_for_vote['title']} ({movie_for_vote['year']})? Type Y/N: ").lower() 
                if voter_response == 'y':
                    ballot_box[voter] = True
                    break
                elif voter_response == 'n':
                    ballot_box[voter] = False
                    break
                else:
                    print("Invalid response! Please enter Y/N.")

        print(ballot_box)

        if any(ballot_box.values()):
            # At least one vote is yes
            print(f"{movie_for_vote['title']} ({movie_for_vote['year']}) was selected.")
            print("It will be marked as Watched automatically.")
            break  # Exit the loop since the movie was accepted
        else:
            # All votes are no
            print(f"{movie_for_vote['title']} ({movie_for_vote['year']}) was REJECTED.")
            print("It will be marked as Skipped automatically.")

            while True:
                another_round = input("Do you want to try finding another random movie? (Y/N) ").lower()
                if another_round == 'y':
                    break  # Loop will continue and pick a new movie
                elif another_round == 'n':
                    print("Good bye!")
                    return  # Exit the function
                else:
                    print("Invalid response. Answer with Y/N.")


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
            vote_on_movie(cursor)


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
