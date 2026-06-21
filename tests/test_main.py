import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import main


PROJECT_DIR = Path(__file__).resolve().parents[1]
MAIN_PATH = PROJECT_DIR / "main.py"


def create_test_connection():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE films (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            year INTEGER NOT NULL,
            status INTEGER NOT NULL DEFAULT 0
        )
        """
    )
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
            main.vote_on_movie(cursor, self.connection, ["Alice", "Bob"])
        status = self.connection.execute("SELECT status FROM films WHERE id = 1").fetchone()[0]
        self.assertEqual(main.STATUS_WATCHED, status)

    def test_second_yes_vote_selects_movie(self):
        cursor = self.connection.cursor()
        with patch("builtins.input", side_effect=["n", "y"]), redirect_stdout(StringIO()):
            main.vote_on_movie(cursor, self.connection, ["Alice", "Bob"])
        status = self.connection.execute("SELECT status FROM films WHERE id = 1").fetchone()[0]
        self.assertEqual(main.STATUS_WATCHED, status)

    def test_all_no_votes_skip_movie(self):
        cursor = self.connection.cursor()
        with patch("builtins.input", side_effect=["n", "n", "n"]), redirect_stdout(StringIO()):
            main.vote_on_movie(cursor, self.connection, ["Alice", "Bob"])
        status = self.connection.execute("SELECT status FROM films WHERE id = 1").fetchone()[0]
        self.assertEqual(main.STATUS_SKIPPED, status)

    def test_invalid_vote_is_reprompted(self):
        cursor = self.connection.cursor()
        output = StringIO()
        with patch("builtins.input", side_effect=["invalid", "y", "n"]), redirect_stdout(output):
            main.vote_on_movie(cursor, self.connection, ["Alice", "Bob"])
        self.assertIn("Invalid response", output.getvalue())

    def test_empty_collection_exits_cleanly(self):
        self.connection.execute("DELETE FROM films")
        output = StringIO()
        with redirect_stdout(output):
            main.vote_on_movie(self.connection.cursor(), self.connection, ["Alice", "Bob"])
        self.assertIn("cleared all the movies", output.getvalue())


class VoterSetupTests(unittest.TestCase):
    def setUp(self):
        self.connection = create_test_connection()

    def tearDown(self):
        self.connection.close()

    def test_first_run_prompts_and_persists_names(self):
        output = StringIO()
        with patch("builtins.input", side_effect=["Alice", "Bob"]), redirect_stdout(output):
            voters = main.get_or_create_voters(self.connection)

        self.assertEqual(["Alice", "Bob"], voters)
        self.assertEqual(["Alice", "Bob"], main.load_voters(self.connection))
        self.assertIn("Voters saved: Alice and Bob", output.getvalue())

    def test_saved_names_are_reused_without_prompting(self):
        main.ensure_voters_table(self.connection)
        self.connection.executemany(
            "INSERT INTO voters (position, name) VALUES (?, ?)",
            ((1, "Alice"), (2, "Bob")),
        )
        self.connection.commit()

        with patch("builtins.input") as mocked_input:
            voters = main.get_or_create_voters(self.connection)

        mocked_input.assert_not_called()
        self.assertEqual(["Alice", "Bob"], voters)

    def test_blank_and_duplicate_names_are_reprompted(self):
        output = StringIO()
        with patch(
            "builtins.input", side_effect=["", "Alice", "alice", "Bob"]
        ), redirect_stdout(output):
            voters = main.get_or_create_voters(self.connection)

        self.assertEqual(["Alice", "Bob"], voters)
        self.assertIn("Name cannot be empty", output.getvalue())
        self.assertIn("Voter names must be different", output.getvalue())

    def test_database_stores_names_but_no_individual_votes(self):
        with patch("builtins.input", side_effect=["Alice", "Bob"]), redirect_stdout(StringIO()):
            main.get_or_create_voters(self.connection)

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


class DatabaseConstraintTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "pm.db"
        shutil.copy2(PROJECT_DIR / "pm.db", self.database_path)
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

    def test_database_path_is_independent_of_working_directory(self):
        with tempfile.TemporaryDirectory() as working_directory:
            result = subprocess.run(
                [sys.executable, str(MAIN_PATH), "listwatched"],
                cwd=working_directory,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertFalse((Path(working_directory) / "pm.db").exists())
        self.assertEqual(0, result.returncode)
        self.assertIn("watched movies", result.stdout)

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
