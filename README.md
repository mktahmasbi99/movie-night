# Movie Night

A two-person command-line program that selects a random unwatched movie, collects a yes/no vote from each person, and updates the movie's status in SQLite.

## Run the program

From the project directory:

```bash
.venv/bin/python main.py --help
.venv/bin/python main.py randommovie
.venv/bin/python main.py listunwatched
.venv/bin/python main.py listwatched
```

## First-time voter setup

Voter names are not hard-coded. The first time `randommovie` runs, the program asks for two different, non-empty names:

```text
Welcome! Let's set up the two voters.
Enter voter 1's name: Alice
Enter voter 2's name: Bob
Voters saved: Alice and Bob.
```

The names are saved in the `voters` table in `pm.db` and reused automatically on later runs. Listing movies and displaying help do not trigger setup.

## Voting behavior

The program always uses two voters:

- If either person votes yes, the movie is marked watched.
- If both people vote no, the movie is marked skipped.
- After a skipped movie, the program can select another random movie.

Votes exist only while the program is processing the current movie. Individual votes and voting history are not written to the database. The database stores only the two display names and the resulting movie status.

## Stored data

`pm.db` contains:

- `films`: movie details and final status (`0` unwatched, `1` skipped, `2` watched).
- `voters`: two ordered display names (`position` and `name` only).

The database rejects unsupported movie statuses, invalid `rewatch_worthy` values, blank voter names, duplicate voter names, and voter positions other than 1 or 2.

## Tests

Run the test suite with:

```bash
.venv/bin/python -m unittest discover -s tests -v
```
