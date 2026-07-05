# Movie Night

Movie Night is a local browser app for choosing what to watch together. It picks a random unwatched movie, collects a yes/no vote from two saved voters, and updates the movie's status in SQLite.

The app stores runtime data in `pm.db`, which is local to your machine and not tracked in Git. A fresh clone can create that database from the tracked seed list at `data/seed-movies.csv`.

## Run the browser app

From the project directory:

```bash
python3 app.py --host 0.0.0.0 --port 5001
```

Then open the forwarded code-server URL, or open the app directly if the port is exposed:

```text
http://localhost:5001
```

For a local-only run on your current machine:

```bash
python3 app.py --host 127.0.0.1 --port 5001
```

## Browser features

- Pick a random unwatched movie in the Tonight view.
- Save two voter names and reuse them automatically.
- Vote yes/no for each voter.
- Mark a movie watched if either voter says yes.
- Mark a movie skipped if both voters say no.
- Browse movies by status: all, unwatched, skipped, watched, and rewatch-worthy.
- Add, edit, and delete movie entries from the Movies view.
- Track rewatch-worthy as a three-state value: blank, yes, or no.
- Create `pm.db` from the seed CSV in the Setup view.

## First-time setup

Open the browser app and go to **Setup**.

1. Create the database from `data/seed-movies.csv`.
2. Save two different, non-empty voter names.
3. Go to **Tonight** and pick a movie.

You can edit `data/seed-movies.csv` before creating the database, or replace it with your own CSV using the same headers:

```csv
id,title,year,director
```

## Terminal commands

The browser app is the main interface, but the terminal commands are still available.

Run the original CLI:

```bash
python3 movie_night.py --help
python3 movie_night.py randommovie
python3 movie_night.py listunwatched
python3 movie_night.py listwatched
```

Create or rebuild the database from the terminal:

```bash
python3 create_database.py
python3 create_database.py --csv path/to/your-movies.csv --db pm.db
python3 create_database.py --replace
```

## Voting behavior

The app always uses two voters:

- If either person votes yes, the movie is marked watched.
- If both people vote no, the movie is marked skipped.
- Individual votes are not saved as history; only the resulting movie status is stored.

## Stored data

The generated `pm.db` contains:

- `films`: movie details, final status (`0` unwatched, `1` skipped, `2` watched), director, and rewatch-worthy metadata.
- `voters`: two ordered display names (`position` and `name` only).

The database rejects unsupported movie statuses, invalid `rewatch_worthy` values, blank voter names, duplicate voter names, and voter positions other than 1 or 2.

## Tests

Run the test suite with:

```bash
python3 -m unittest discover -s tests -v
```
