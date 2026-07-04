# Movie Night

A two-person command-line program that selects a random unwatched movie, collects a yes/no vote from each person, and updates the movie's status in SQLite.

`pm.db` is a local runtime database and is not tracked in Git. A fresh clone can create it from the tracked seed list at `data/seed-movies.csv`.

## Run the program

From the project directory:

```bash
.venv/bin/python movie_night.py --help
.venv/bin/python movie_night.py randommovie
.venv/bin/python movie_night.py listunwatched
.venv/bin/python movie_night.py listwatched
```

## First-time database setup

The first time you run a movie command without `pm.db`, the app asks whether to create the database from `data/seed-movies.csv`. You can edit that CSV first, or replace it with your own CSV using the same headers:

```csv
id,title,year,director
```

You can also create the database directly:

```bash
.venv/bin/python create_database.py
.venv/bin/python create_database.py --csv path/to/your-movies.csv --db pm.db
```

If `pm.db` already exists, pass `--replace` to rebuild the film rows from CSV.

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

The generated `pm.db` contains:

- `films`: movie details and final status (`0` unwatched, `1` skipped, `2` watched).
- `voters`: two ordered display names (`position` and `name` only).

The database rejects unsupported movie statuses, invalid `rewatch_worthy` values, blank voter names, duplicate voter names, and voter positions other than 1 or 2.

## Tests

Run the test suite with:

```bash
.venv/bin/python -m unittest discover -s tests -v
```
