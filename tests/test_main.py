import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import movie_night
import app


PROJECT_DIR = Path(__file__).resolve().parents[1]
MAIN_PATH = PROJECT_DIR / "movie_night.py"


def create_test_connection():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    movie_night.ensure_films_table(connection)
    return connection


class VotingTests(unittest.TestCase):
    def setUp(self):
        self.connection = create_test_connection()
        self.connection.execute(
            "INSERT INTO films (id, title, year, status) VALUES (1, 'Test Film', 2024, 0)"
        )
        self.connection.commit()

    def tearDown(self):
        self.connection.close()

    def test_one_yes_vote_selects_movie(self):
        cursor = self.connection.cursor()
        with patch("builtins.input", side_effect=["y", "n"]), redirect_stdout(StringIO()):
            movie_night.vote_on_movie(cursor, self.connection, ["Alice", "Bob"])
        status = self.connection.execute("SELECT status FROM films WHERE id = 1").fetchone()[0]
        self.assertEqual(movie_night.STATUS_WATCHED, status)

    def test_second_yes_vote_selects_movie(self):
        cursor = self.connection.cursor()
        with patch("builtins.input", side_effect=["n", "y"]), redirect_stdout(StringIO()):
            movie_night.vote_on_movie(cursor, self.connection, ["Alice", "Bob"])
        status = self.connection.execute("SELECT status FROM films WHERE id = 1").fetchone()[0]
        self.assertEqual(movie_night.STATUS_WATCHED, status)

    def test_all_no_votes_skip_movie(self):
        cursor = self.connection.cursor()
        with patch("builtins.input", side_effect=["n", "n", "n"]), redirect_stdout(StringIO()):
            movie_night.vote_on_movie(cursor, self.connection, ["Alice", "Bob"])
        status = self.connection.execute("SELECT status FROM films WHERE id = 1").fetchone()[0]
        self.assertEqual(movie_night.STATUS_SKIPPED, status)

    def test_invalid_vote_is_reprompted(self):
        cursor = self.connection.cursor()
        output = StringIO()
        with patch("builtins.input", side_effect=["invalid", "y", "n"]), redirect_stdout(output):
            movie_night.vote_on_movie(cursor, self.connection, ["Alice", "Bob"])
        self.assertIn("Invalid response", output.getvalue())

    def test_empty_collection_exits_cleanly(self):
        self.connection.execute("DELETE FROM films")
        output = StringIO()
        with redirect_stdout(output):
            movie_night.vote_on_movie(self.connection.cursor(), self.connection, ["Alice", "Bob"])
        self.assertIn("cleared all the movies", output.getvalue())


class VoterSetupTests(unittest.TestCase):
    def setUp(self):
        self.connection = create_test_connection()

    def tearDown(self):
        self.connection.close()

    def test_first_run_prompts_and_persists_names(self):
        output = StringIO()
        with patch("builtins.input", side_effect=["Alice", "Bob"]), redirect_stdout(output):
            voters = movie_night.get_or_create_voters(self.connection)

        self.assertEqual(["Alice", "Bob"], voters)
        self.assertEqual(["Alice", "Bob"], movie_night.load_voters(self.connection))
        self.assertIn("Voters saved: Alice and Bob", output.getvalue())

    def test_saved_names_are_reused_without_prompting(self):
        movie_night.ensure_voters_table(self.connection)
        self.connection.executemany(
            "INSERT INTO voters (position, name) VALUES (?, ?)",
            ((1, "Alice"), (2, "Bob")),
        )
        self.connection.commit()

        with patch("builtins.input") as mocked_input:
            voters = movie_night.get_or_create_voters(self.connection)

        mocked_input.assert_not_called()
        self.assertEqual(["Alice", "Bob"], voters)

    def test_blank_and_duplicate_names_are_reprompted(self):
        output = StringIO()
        with patch(
            "builtins.input", side_effect=["", "Alice", "alice", "Bob"]
        ), redirect_stdout(output):
            voters = movie_night.get_or_create_voters(self.connection)

        self.assertEqual(["Alice", "Bob"], voters)
        self.assertIn("Name cannot be empty", output.getvalue())
        self.assertIn("Voter names must be different", output.getvalue())

    def test_database_stores_names_but_no_individual_votes(self):
        with patch("builtins.input", side_effect=["Alice", "Bob"]), redirect_stdout(StringIO()):
            movie_night.get_or_create_voters(self.connection)

        tables = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        columns = {
            row[1] for row in self.connection.execute("PRAGMA table_info(voters)")
        }

        self.assertEqual({"position", "name"}, columns)
        self.assertNotIn("votes", tables)


class SeedDatabaseTests(unittest.TestCase):
    def test_seed_csv_can_create_database(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "pm.db"
            movie_count = movie_night.create_database_from_csv(
                database_path, PROJECT_DIR / "data" / "seed-movies.csv"
            )
            connection = sqlite3.connect(database_path)
            try:
                stored_count = connection.execute("SELECT COUNT(*) FROM films").fetchone()[0]
                columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(films)")
                }
                rewatch_count = connection.execute(
                    "SELECT COUNT(*) FROM films WHERE rewatch_worthy IS NULL"
                ).fetchone()[0]
            finally:
                connection.close()

        self.assertEqual(365, movie_count)
        self.assertEqual(movie_count, stored_count)
        self.assertEqual(movie_count, rewatch_count)
        self.assertIn("director", columns)
        self.assertIn("rewatch_worthy", columns)

    def test_first_run_setup_can_seed_missing_database(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "pm.db"
            output = StringIO()
            with patch("builtins.input", side_effect=["y"]), redirect_stdout(output):
                result = movie_night.main(["listunwatched"], db_path=database_path)

        self.assertEqual(0, result)
        self.assertIn("Created pm.db with 365 movies", output.getvalue())
        self.assertIn("Here are your unwatched movies", output.getvalue())

    def test_first_run_setup_can_be_declined(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "pm.db"
            output = StringIO()
            with patch("builtins.input", side_effect=["n"]), redirect_stdout(output):
                result = movie_night.main(["listunwatched"], db_path=database_path)

        self.assertEqual(1, result)
        self.assertIn("Database setup skipped", output.getvalue())

    def test_existing_database_is_used_without_seed_or_schema_changes(self):
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute(
                """
                CREATE TABLE films (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    status INTEGER NOT NULL DEFAULT 0
                );
                """
            )
            connection.execute(
                """
                INSERT INTO films (id, title, year, status)
                VALUES (1, 'Trip to the Moon', 1902, ?)
                """,
                (movie_night.STATUS_WATCHED,),
            )
            connection.commit()

            self.assertTrue(movie_night.ensure_database_ready(connection))

            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(films)")
            }
            status = connection.execute(
                "SELECT status FROM films WHERE id = 1"
            ).fetchone()[0]
        finally:
            connection.close()

        self.assertEqual({"id", "title", "year", "status"}, columns)
        self.assertEqual(movie_night.STATUS_WATCHED, status)


class WebApiSerializationTests(unittest.TestCase):
    def test_rewatch_worthy_preserves_three_states(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            movie_night.ensure_films_table(connection)
            connection.executemany(
                """
                INSERT INTO films (id, title, year, status, rewatch_worthy)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    (1, "Unknown", 2024, movie_night.STATUS_UNWATCHED, None),
                    (2, "No", 2024, movie_night.STATUS_UNWATCHED, 0),
                    (3, "Yes", 2024, movie_night.STATUS_UNWATCHED, 1),
                ),
            )
            movies = app.list_movies(connection)
        finally:
            connection.close()

        values = {movie["title"]: movie["rewatchWorthy"] for movie in movies}
        self.assertIsNone(values["Unknown"])
        self.assertEqual(0, values["No"])
        self.assertEqual(1, values["Yes"])


class DatabaseConstraintTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "pm.db"
        movie_night.create_database_from_csv(
            self.database_path, PROJECT_DIR / "data" / "seed-movies.csv"
        )
        self.connection = sqlite3.connect(self.database_path)

    def tearDown(self):
        self.connection.close()
        self.temporary_directory.cleanup()

    def test_invalid_status_is_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute("UPDATE films SET status = 99 WHERE id = 1")

    def test_invalid_rewatch_value_is_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "UPDATE films SET rewatch_worthy = -1 WHERE id = 1"
            )

    def test_valid_constraint_values_are_accepted(self):
        self.connection.execute(
            "UPDATE films SET status = 2, rewatch_worthy = 1 WHERE id = 1"
        )
        values = self.connection.execute(
            "SELECT status, rewatch_worthy FROM films WHERE id = 1"
        ).fetchone()
        self.assertEqual((2, 1), values)

    def test_null_rewatch_value_is_accepted(self):
        self.connection.execute("UPDATE films SET rewatch_worthy = NULL WHERE id = 1")
        value = self.connection.execute(
            "SELECT rewatch_worthy FROM films WHERE id = 1"
        ).fetchone()[0]
        self.assertIsNone(value)


class CommandLineTests(unittest.TestCase):
    def test_help_works_outside_project_directory(self):
        with tempfile.TemporaryDirectory() as working_directory:
            result = subprocess.run(
                [sys.executable, str(MAIN_PATH), "--help"],
                cwd=working_directory,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(0, result.returncode)
        self.assertIn("randommovie", result.stdout)

    def test_declined_database_setup_does_not_create_db_in_working_directory(self):
        with tempfile.TemporaryDirectory() as working_directory:
            database_path = Path(working_directory) / "custom-pm.db"
            env = {**os.environ, "MOVIE_NIGHT_DB_PATH": str(database_path)}
            result = subprocess.run(
                [sys.executable, str(MAIN_PATH), "listwatched"],
                cwd=working_directory,
                input="n\n",
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertFalse((Path(working_directory) / "pm.db").exists())
        self.assertEqual(1, result.returncode)
        self.assertIn("Database setup skipped", result.stdout)

    def test_unknown_command_is_rejected(self):
        result = subprocess.run(
            [sys.executable, str(MAIN_PATH), "unknown"],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("invalid choice", result.stderr)

    def test_extra_arguments_are_rejected(self):
        result = subprocess.run(
            [sys.executable, str(MAIN_PATH), "listwatched", "extra"],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("unrecognized arguments", result.stderr)


if __name__ == "__main__":
    unittest.main()
