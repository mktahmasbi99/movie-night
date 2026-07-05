import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import movie_night


STATUS_LABELS = {
    movie_night.STATUS_UNWATCHED: "Unwatched",
    movie_night.STATUS_SKIPPED: "Skipped",
    movie_night.STATUS_WATCHED: "Watched",
}

CURRENT_PICK = None
CURRENT_VOTES = {}


def row_to_movie(row):
    """Convert a SQLite row into a JSON-friendly movie dictionary."""
    return {
        "id": row["id"],
        "title": row["title"],
        "year": row["year"],
        "director": row["director"],
        "status": row["status"],
        "statusLabel": STATUS_LABELS[row["status"]],
        "rewatchWorthy": row["rewatch_worthy"],
    }


def get_counts(conn):
    rows = conn.execute(
        """
        SELECT status, COUNT(*) AS count
        FROM films
        GROUP BY status;
        """
    ).fetchall()
    counts = {"unwatched": 0, "skipped": 0, "watched": 0}
    for row in rows:
        if row["status"] == movie_night.STATUS_UNWATCHED:
            counts["unwatched"] = row["count"]
        elif row["status"] == movie_night.STATUS_SKIPPED:
            counts["skipped"] = row["count"]
        elif row["status"] == movie_night.STATUS_WATCHED:
            counts["watched"] = row["count"]
    return counts


def database_exists(conn):
    return movie_night.has_table(conn, "films")


def get_voters(conn):
    movie_night.ensure_voters_table(conn)
    return movie_night.load_voters(conn)


def list_movies(conn, status_filter="all"):
    status_values = {
        "unwatched": movie_night.STATUS_UNWATCHED,
        "skipped": movie_night.STATUS_SKIPPED,
        "watched": movie_night.STATUS_WATCHED,
    }
    if status_filter in status_values:
        rows = conn.execute(
            """
            SELECT *
            FROM films
            WHERE status = ?
            ORDER BY year, title;
            """,
            (status_values[status_filter],),
        ).fetchall()
    elif status_filter == "rewatch-worthy":
        rows = conn.execute(
            """
            SELECT *
            FROM films
            WHERE rewatch_worthy = 1
            ORDER BY year, title;
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT *
            FROM films
            ORDER BY status, year, title;
            """
        ).fetchall()
    return [row_to_movie(row) for row in rows]


def response_state(conn):
    has_database = database_exists(conn)
    voters = get_voters(conn)
    state = {
        "hasDatabase": has_database,
        "voters": voters,
        "needsVoters": len(voters) != 2,
        "currentPick": CURRENT_PICK,
        "votes": CURRENT_VOTES,
        "counts": {"unwatched": 0, "skipped": 0, "watched": 0},
    }
    if has_database:
        state["counts"] = get_counts(conn)
    return state


def clean_movie_payload(payload):
    title = str(payload.get("title", "")).strip() or None

    year_value = payload.get("year")
    if year_value in ("", None):
        year = None
    else:
        try:
            year = int(year_value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Year must be a number or blank.") from exc

    try:
        status = int(payload.get("status"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Status is required.") from exc
    if status not in STATUS_LABELS:
        raise ValueError("Unknown movie status.")

    rewatch_worthy = payload.get("rewatchWorthy")
    if rewatch_worthy in ("", None):
        rewatch_worthy = None
    else:
        try:
            rewatch_worthy = int(rewatch_worthy)
        except (TypeError, ValueError) as exc:
            raise ValueError("Rewatch-Worthy must be Yes, No, or blank.") from exc
        if rewatch_worthy not in (0, 1):
            raise ValueError("Rewatch-Worthy must be Yes, No, or blank.")

    director = str(payload.get("director", "")).strip() or None
    return {
        "title": title,
        "year": year,
        "director": director,
        "status": status,
        "rewatch_worthy": rewatch_worthy,
    }


def fetch_movie(conn, movie_id):
    row = conn.execute("SELECT * FROM films WHERE id = ?;", (movie_id,)).fetchone()
    if row is None:
        raise ValueError("Movie not found.")
    return row_to_movie(row)


def save_movie(conn, payload):
    global CURRENT_PICK, CURRENT_VOTES

    movie_id = payload.get("id")
    is_edit = movie_id not in (None, "")
    if is_edit and payload.get("confirmation") != "CONFIRM":
        raise ValueError("Type CONFIRM to save changes.")

    movie = clean_movie_payload(payload)
    with conn:
        if not is_edit:
            cursor = conn.execute(
                """
                INSERT INTO films (title, year, director, status, rewatch_worthy)
                VALUES (?, ?, ?, ?, ?);
                """,
                (
                    movie["title"],
                    movie["year"],
                    movie["director"],
                    movie["status"],
                    movie["rewatch_worthy"],
                ),
            )
            saved_id = cursor.lastrowid
        else:
            try:
                saved_id = int(movie_id)
            except (TypeError, ValueError) as exc:
                raise ValueError("Movie id must be a number.") from exc
            cursor = conn.execute(
                """
                UPDATE films
                SET title = ?, year = ?, director = ?, status = ?, rewatch_worthy = ?
                WHERE id = ?;
                """,
                (
                    movie["title"],
                    movie["year"],
                    movie["director"],
                    movie["status"],
                    movie["rewatch_worthy"],
                    saved_id,
                ),
            )
            if cursor.rowcount == 0:
                raise ValueError("Movie not found.")

    saved_movie = fetch_movie(conn, saved_id)
    if CURRENT_PICK and CURRENT_PICK["id"] == saved_id:
        CURRENT_PICK = saved_movie
        CURRENT_VOTES = {}
    return saved_movie


def delete_movie(conn, payload):
    global CURRENT_PICK, CURRENT_VOTES

    if payload.get("confirmation") != "DELETE":
        raise ValueError("Type DELETE to delete this movie.")
    try:
        movie_id = int(payload.get("id"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Movie id must be a number.") from exc

    with conn:
        cursor = conn.execute("DELETE FROM films WHERE id = ?;", (movie_id,))
        if cursor.rowcount == 0:
            raise ValueError("Movie not found.")

    if CURRENT_PICK and CURRENT_PICK["id"] == movie_id:
        CURRENT_PICK = None
        CURRENT_VOTES = {}
    return {"deleted": movie_id}


def save_voters(conn, voters):
    clean_voters = [voter.strip() for voter in voters]
    if len(clean_voters) != 2 or not all(clean_voters):
        raise ValueError("Enter two voter names.")
    if clean_voters[0].casefold() == clean_voters[1].casefold():
        raise ValueError("Voter names must be different.")

    movie_night.ensure_voters_table(conn)
    with conn:
        conn.execute("DELETE FROM voters;")
        conn.executemany(
            "INSERT INTO voters (position, name) VALUES (?, ?);",
            ((1, clean_voters[0]), (2, clean_voters[1])),
        )
    return clean_voters


def select_pick(conn):
    global CURRENT_PICK, CURRENT_VOTES

    if not database_exists(conn):
        raise ValueError("Create the database first.")

    movie = movie_night.select_random(conn.cursor())
    if movie is None:
        CURRENT_PICK = None
        CURRENT_VOTES = {}
        return None

    CURRENT_PICK = row_to_movie(movie)
    CURRENT_VOTES = {}
    return CURRENT_PICK


def record_vote(conn, voter, vote):
    global CURRENT_PICK, CURRENT_VOTES

    if CURRENT_PICK is None:
        raise ValueError("Pick a movie first.")

    voters = get_voters(conn)
    if voter not in voters:
        raise ValueError("Unknown voter.")

    CURRENT_VOTES[voter] = bool(vote)
    result = None
    if len(CURRENT_VOTES) == 2:
        selected = any(CURRENT_VOTES.values())
        status = (
            movie_night.STATUS_WATCHED
            if selected
            else movie_night.STATUS_SKIPPED
        )
        movie_night.update_movie_status(
            conn.cursor(), CURRENT_PICK["id"], status
        )
        conn.commit()
        CURRENT_PICK["status"] = status
        CURRENT_PICK["statusLabel"] = STATUS_LABELS[status]
        result = "watched" if selected else "skipped"

    return {"votes": CURRENT_VOTES, "result": result, "currentPick": CURRENT_PICK}


class MovieNightHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_html(INDEX_HTML)
        elif parsed.path == "/api/state":
            self.with_connection(lambda conn: response_state(conn))
        elif parsed.path == "/api/movies":
            query = parse_qs(parsed.query)
            status_filter = query.get("status", ["all"])[0]
            self.with_connection(lambda conn: {"movies": list_movies(conn, status_filter)})
        else:
            self.send_error(404, "Not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/setup-database":
            self.with_connection(self.handle_setup_database)
        elif parsed.path == "/api/voters":
            payload = self.read_json()
            self.with_connection(lambda conn: {"voters": save_voters(conn, payload["voters"])})
        elif parsed.path == "/api/pick":
            self.with_connection(lambda conn: {"movie": select_pick(conn)})
        elif parsed.path == "/api/vote":
            payload = self.read_json()
            self.with_connection(
                lambda conn: record_vote(conn, payload["voter"], payload["vote"])
            )
        elif parsed.path == "/api/movie":
            payload = self.read_json()
            self.with_connection(lambda conn: {"movie": save_movie(conn, payload)})
        elif parsed.path == "/api/movie/delete":
            payload = self.read_json()
            self.with_connection(lambda conn: delete_movie(conn, payload))
        else:
            self.send_error(404, "Not found")

    def handle_setup_database(self, conn):
        movie_count = movie_night.create_database_from_csv()
        return {
            "message": f"Created pm.db with {movie_count} movies.",
            "state": response_state(conn),
        }

    def with_connection(self, callback):
        conn = movie_night.get_connection()
        try:
            result = callback(conn)
        except (KeyError, ValueError) as exc:
            self.send_json({"error": str(exc)}, status=400)
        finally:
            conn.close()
        if "result" in locals():
            self.send_json(result)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body)

    def send_html(self, body):
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_json(self, body, status=200):
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        return


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Movie Night</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #101216;
      --panel: #191d23;
      --panel-strong: #202630;
      --line: #343b46;
      --text: #f5f0e8;
      --muted: #aeb6c2;
      --accent: #d8a84e;
      --green: #7fcf8f;
      --red: #e17a7a;
      --blue: #80a8ff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    button, input, select { font: inherit; }
    button {
      border: 1px solid var(--line);
      border-radius: 7px;
      color: var(--text);
      background: var(--panel-strong);
      min-height: 42px;
      padding: 0 14px;
      cursor: pointer;
    }
    button:hover { border-color: var(--accent); }
    button.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: #17130b;
      font-weight: 700;
    }
    button.yes { border-color: rgba(127, 207, 143, 0.55); }
    button.no { border-color: rgba(225, 122, 122, 0.55); }
    button[disabled] {
      cursor: not-allowed;
      opacity: 0.55;
    }
    input, select {
      width: 100%;
      min-height: 42px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #11151b;
      color: var(--text);
      padding: 0 12px;
    }
    .shell {
      max-width: 1160px;
      margin: 0 auto;
      padding: 24px;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
    }
    h1, h2, h3, p { margin-top: 0; }
    h1 {
      margin-bottom: 4px;
      font-size: clamp(28px, 4vw, 48px);
      line-height: 1;
    }
    h2 { font-size: 20px; margin-bottom: 14px; }
    h3 { font-size: 16px; margin-bottom: 8px; }
    .subtitle { color: var(--muted); margin-bottom: 0; }
    .tabs {
      display: flex;
      gap: 8px;
      border-bottom: 1px solid var(--line);
      margin-bottom: 20px;
      overflow-x: auto;
    }
    .tab {
      border: 0;
      border-bottom: 3px solid transparent;
      border-radius: 0;
      background: transparent;
      color: var(--muted);
      min-width: 110px;
    }
    .tab.active {
      color: var(--text);
      border-bottom-color: var(--accent);
    }
    .view { display: none; }
    .view.active { display: block; }
    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.8fr);
      gap: 16px;
      align-items: start;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
    }
    .movie-title {
      font-size: clamp(30px, 5vw, 58px);
      line-height: 1.02;
      margin-bottom: 10px;
    }
    .meta {
      color: var(--muted);
      display: flex;
      flex-wrap: wrap;
      gap: 8px 14px;
      margin-bottom: 22px;
    }
    .status {
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 0 10px;
      color: var(--muted);
    }
    .status.Watched { color: var(--green); }
    .status.Skipped { color: var(--red); }
    .status.Unwatched { color: var(--blue); }
    .status.Yes { color: var(--green); }
    .status.No { color: var(--red); }
    .voters {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin-top: 18px;
    }
    .voter {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: #13171d;
    }
    .vote-actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-top: 12px;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
    }
    .stat {
      background: #12171d;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
    }
    .stat strong {
      display: block;
      font-size: 26px;
    }
    .stat span { color: var(--muted); font-size: 13px; }
    .setup-form {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr)) auto;
      gap: 10px;
      align-items: end;
    }
    .toolbar {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
      align-items: center;
    }
    .toolbar-actions {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .toolbar-actions select { min-width: 190px; }
    .table-action { min-height: 34px; padding: 0 10px; }
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(4, 6, 10, 0.76);
      display: none;
      align-items: center;
      justify-content: center;
      padding: 20px;
      z-index: 10;
    }
    .modal-backdrop.active { display: flex; }
    .modal {
      width: min(760px, 100%);
      max-height: calc(100vh - 40px);
      overflow: auto;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      box-shadow: 0 24px 70px rgba(0, 0, 0, 0.45);
    }
    .movie-form {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .movie-form .full { grid-column: 1 / -1; }
    .modal-actions {
      display: flex;
      gap: 10px;
      justify-content: flex-end;
      flex-wrap: wrap;
      margin-top: 14px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
    }
    th, td {
      border-bottom: 1px solid var(--line);
      padding: 11px 10px;
      text-align: left;
      vertical-align: top;
    }
    th {
      color: var(--muted);
      font-size: 13px;
      font-weight: 600;
    }
    .message {
      min-height: 24px;
      color: var(--muted);
      margin-top: 12px;
    }
    .message.error { color: var(--red); }
    .empty {
      color: var(--muted);
      padding: 24px 0;
    }
    @media (max-width: 820px) {
      .shell { padding: 16px; }
      header { display: block; }
      .grid, .voters, .setup-form, .movie-form { grid-template-columns: 1fr; }
      .stats { grid-template-columns: 1fr; }
      table { font-size: 14px; }
      th:nth-child(3), td:nth-child(3) { display: none; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div>
        <h1>Movie Night</h1>
        <p class="subtitle">Pick a movie, collect two votes, keep the list moving.</p>
      </div>
    </header>

    <nav class="tabs" aria-label="Main views">
      <button class="tab active" data-view="tonight">Tonight</button>
      <button class="tab" data-view="movies">Movies</button>
      <button class="tab" data-view="setup">Setup</button>
    </nav>

    <main>
      <section class="view active" id="tonight">
        <div class="grid">
          <section class="panel">
            <div class="toolbar">
              <h2>Tonight's Pick</h2>
              <button class="primary" id="pickButton">Pick Movie</button>
            </div>
            <div id="movieStage">
              <p class="empty">No movie picked yet.</p>
            </div>
          </section>
          <aside class="panel">
            <h2>Library</h2>
            <div class="stats">
              <div class="stat"><strong id="unwatchedCount">0</strong><span>Unwatched</span></div>
              <div class="stat"><strong id="skippedCount">0</strong><span>Skipped</span></div>
              <div class="stat"><strong id="watchedCount">0</strong><span>Watched</span></div>
            </div>
            <p class="message" id="tonightMessage"></p>
          </aside>
        </div>
      </section>

      <section class="view" id="movies">
        <section class="panel">
          <div class="toolbar">
            <h2>Movies</h2>
            <div class="toolbar-actions">
              <select id="movieFilter" aria-label="Movie status filter">
                <option value="all">All movies</option>
                <option value="unwatched">Unwatched</option>
                <option value="skipped">Skipped</option>
                <option value="watched">Watched</option>
                <option value="rewatch-worthy">Rewatch-Worthy</option>
              </select>
              <button id="addMovieButton">Add Movie</button>
            </div>
          </div>
          <div id="movieTable"></div>
        </section>
      </section>

      <section class="view" id="setup">
        <section class="panel">
          <h2>Setup</h2>
          <p class="subtitle">Use the seed CSV to create the local database, then save the two voters.</p>
          <p>
            <button id="setupDatabaseButton">Create Database From Seed CSV</button>
          </p>
          <form class="setup-form" id="voterForm">
            <label>
              Voter 1
              <input id="voterOne" name="voterOne" autocomplete="off">
            </label>
            <label>
              Voter 2
              <input id="voterTwo" name="voterTwo" autocomplete="off">
            </label>
            <button class="primary" type="submit">Save Voters</button>
          </form>
          <p class="message" id="setupMessage"></p>
        </section>
      </section>
    </main>
  </div>

  <div class="modal-backdrop" id="movieModal" aria-hidden="true">
    <section class="modal" role="dialog" aria-modal="true" aria-labelledby="movieEditorTitle">
      <div class="toolbar">
        <h2 id="movieEditorTitle">Edit Movie</h2>
        <button id="closeMovieModal" type="button">Close</button>
      </div>
      <form class="movie-form" id="movieForm">
        <input id="movieId" type="hidden">
        <label class="full">
          Title
          <input id="movieTitle">
        </label>
        <label>
          Year
          <input id="movieYear" inputmode="numeric">
        </label>
        <label>
          Status
          <select id="movieStatus">
            <option value="0">Unwatched</option>
            <option value="1">Skipped</option>
            <option value="2">Watched</option>
          </select>
        </label>
        <label>
          Director
          <input id="movieDirector">
        </label>
        <label>
          Rewatch-Worthy
          <select id="movieRewatch">
            <option value="">Unset</option>
            <option value="1">Yes</option>
            <option value="0">No</option>
          </select>
        </label>
        <label class="full" id="movieConfirmationGroup">
          Confirmation
          <input id="movieConfirmation" autocomplete="off" placeholder="CONFIRM to save, DELETE to delete">
        </label>
        <p class="message full" id="movieEditorMessage"></p>
        <div class="modal-actions full">
          <button id="deleteMovieButton" class="no" type="button">Delete Movie</button>
          <button class="primary" id="saveMovieButton" type="submit">Save Changes</button>
        </div>
      </form>
    </section>
  </div>

  <script>
    const app = {
      state: null,
      movieFilter: "all",
      movies: [],
    };

    const $ = (selector) => document.querySelector(selector);

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: { "Content-Type": "application/json" },
        ...options,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Request failed");
      return data;
    }

    function setMessage(selector, text, isError = false) {
      const element = $(selector);
      element.textContent = text || "";
      element.classList.toggle("error", isError);
    }

    function setEditorMessage(text, isError = false) {
      setMessage("#movieEditorMessage", text, isError);
    }

    function openMovieEditor(movie = null) {
      const isEdit = Boolean(movie);
      $("#movieEditorTitle").textContent = isEdit ? "Edit Movie" : "Add Movie";
      $("#movieId").value = movie ? movie.id : "";
      $("#movieTitle").value = movie ? movie.title : "";
      $("#movieYear").value = movie ? movie.year : "";
      $("#movieDirector").value = movie && movie.director ? movie.director : "";
      $("#movieStatus").value = movie ? String(movie.status) : "0";
      $("#movieRewatch").value = movie && movie.rewatchWorthy !== null ? String(movie.rewatchWorthy) : "";
      $("#movieConfirmation").value = "";
      $("#movieConfirmationGroup").style.display = isEdit ? "block" : "none";
      $("#deleteMovieButton").style.display = isEdit ? "inline-flex" : "none";
      $("#saveMovieButton").textContent = isEdit ? "Save Changes" : "Add Movie";
      setEditorMessage("");
      $("#movieModal").classList.add("active");
      $("#movieModal").setAttribute("aria-hidden", "false");
      $("#movieTitle").focus();
    }

    function closeMovieEditor() {
      $("#movieModal").classList.remove("active");
      $("#movieModal").setAttribute("aria-hidden", "true");
    }

    function moviePayload() {
      const rewatchValue = $("#movieRewatch").value;
      return {
        id: $("#movieId").value,
        title: $("#movieTitle").value,
        year: $("#movieYear").value,
        director: $("#movieDirector").value,
        status: Number($("#movieStatus").value),
        rewatchWorthy: rewatchValue === "" ? null : Number(rewatchValue),
        confirmation: $("#movieConfirmation").value,
      };
    }

    function statusBadge(movie) {
      return `<span class="status ${movie.statusLabel}">${movie.statusLabel}</span>`;
    }

    function rewatchBadge(movie) {
      if (movie.rewatchWorthy === null) return "";
      const label = movie.rewatchWorthy === 1 ? "Yes" : "No";
      return `<span class="status ${label}">${label}</span>`;
    }

    function renderState() {
      const { counts, voters, currentPick, votes, hasDatabase, needsVoters } = app.state;
      $("#unwatchedCount").textContent = counts.unwatched;
      $("#skippedCount").textContent = counts.skipped;
      $("#watchedCount").textContent = counts.watched;
      $("#pickButton").disabled = !hasDatabase || needsVoters;
      $("#voterOne").value = voters[0] || "";
      $("#voterTwo").value = voters[1] || "";

      if (!hasDatabase) {
        $("#movieStage").innerHTML = `<p class="empty">No database yet. Go to Setup and create it from the seed CSV.</p>`;
        return;
      }
      if (needsVoters) {
        $("#movieStage").innerHTML = `<p class="empty">Add two voter names in Setup before picking a movie.</p>`;
        return;
      }
      if (!currentPick) {
        $("#movieStage").innerHTML = `<p class="empty">No movie picked yet.</p>`;
        return;
      }

      const voterCards = voters.map((voter) => {
        const vote = votes[voter];
        const voteLabel = vote === true ? "Yes" : vote === false ? "No" : "Waiting";
        const disabled = vote !== undefined || currentPick.statusLabel !== "Unwatched";
        return `
          <div class="voter">
            <h3>${escapeHtml(voter)}</h3>
            <p class="subtitle">${voteLabel}</p>
            <div class="vote-actions">
              <button class="yes" ${disabled ? "disabled" : ""} data-vote="yes" data-voter="${escapeHtml(voter)}">Yes</button>
              <button class="no" ${disabled ? "disabled" : ""} data-vote="no" data-voter="${escapeHtml(voter)}">No</button>
            </div>
          </div>
        `;
      }).join("");

      $("#movieStage").innerHTML = `
        <div class="movie-title">${escapeHtml(currentPick.title || "Untitled")}</div>
        <div class="meta">
          ${currentPick.year === null ? "" : `<span>${currentPick.year}</span>`}
          <span>${escapeHtml(currentPick.director || "Unknown director")}</span>
          ${statusBadge(currentPick)}
        </div>
        <div class="voters">${voterCards}</div>
      `;
    }

    async function loadState() {
      app.state = await api("api/state");
      renderState();
    }

    async function loadMovies() {
      const data = await api(`api/movies?status=${encodeURIComponent(app.movieFilter)}`);
      app.movies = data.movies;
      if (!data.movies.length) {
        $("#movieTable").innerHTML = `<p class="empty">No movies found.</p>`;
        return;
      }
      const rows = data.movies.map((movie) => `
        <tr>
          <td>${escapeHtml(movie.title || "")}</td>
          <td>${movie.year === null ? "" : movie.year}</td>
          <td>${escapeHtml(movie.director || "")}</td>
          <td>${rewatchBadge(movie)}</td>
          <td>${statusBadge(movie)}</td>
          <td><button class="table-action" data-edit-movie="${movie.id}">Edit</button></td>
        </tr>
      `).join("");
      $("#movieTable").innerHTML = `
        <table>
          <thead>
            <tr><th>Title</th><th>Year</th><th>Director</th><th>Rewatch-Worthy</th><th>Status</th><th>Actions</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      `;
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    document.addEventListener("click", async (event) => {
      const tab = event.target.closest(".tab");
      if (tab) {
        document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
        document.querySelectorAll(".view").forEach((item) => item.classList.remove("active"));
        tab.classList.add("active");
        $(`#${tab.dataset.view}`).classList.add("active");
        if (tab.dataset.view === "movies") loadMovies();
        return;
      }

      if (event.target.id === "addMovieButton") {
        openMovieEditor();
        return;
      }

      const editButton = event.target.closest("[data-edit-movie]");
      if (editButton) {
        const movieId = Number(editButton.dataset.editMovie);
        const movie = app.movies.find((item) => item.id === movieId);
        if (movie) openMovieEditor(movie);
        return;
      }

      if (event.target.id === "closeMovieModal") {
        closeMovieEditor();
        return;
      }

      if (event.target.id === "deleteMovieButton") {
        try {
          const payload = { id: $("#movieId").value, confirmation: $("#movieConfirmation").value };
          await api("api/movie/delete", {
            method: "POST",
            body: JSON.stringify(payload),
          });
          closeMovieEditor();
          await loadState();
          await loadMovies();
        } catch (error) {
          setEditorMessage(error.message, true);
        }
        return;
      }

      if (event.target.id === "pickButton") {
        try {
          const data = await api("api/pick", { method: "POST" });
          await loadState();
          await loadMovies();
          setMessage("#tonightMessage", data.movie ? "Movie picked." : "You've cleared all the movies.");
        } catch (error) {
          setMessage("#tonightMessage", error.message, true);
        }
      }

      if (event.target.id === "setupDatabaseButton") {
        try {
          const data = await api("api/setup-database", { method: "POST" });
          await loadState();
          await loadMovies();
          setMessage("#setupMessage", data.message);
        } catch (error) {
          setMessage("#setupMessage", error.message, true);
        }
      }

      const voteButton = event.target.closest("[data-vote]");
      if (voteButton) {
        try {
          const payload = {
            voter: voteButton.dataset.voter,
            vote: voteButton.dataset.vote === "yes",
          };
          const data = await api("api/vote", {
            method: "POST",
            body: JSON.stringify(payload),
          });
          await loadState();
          await loadMovies();
          if (data.result === "watched") setMessage("#tonightMessage", "Selected. Marked as watched.");
          else if (data.result === "skipped") setMessage("#tonightMessage", "Rejected. Marked as skipped.");
          else setMessage("#tonightMessage", "Vote saved.");
        } catch (error) {
          setMessage("#tonightMessage", error.message, true);
        }
      }
    });

    $("#movieFilter").addEventListener("change", (event) => {
      app.movieFilter = event.target.value;
      loadMovies();
    });

    $("#movieForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        await api("api/movie", {
          method: "POST",
          body: JSON.stringify(moviePayload()),
        });
        closeMovieEditor();
        await loadState();
        await loadMovies();
      } catch (error) {
        setEditorMessage(error.message, true);
      }
    });

    $("#voterForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const voters = [$("#voterOne").value, $("#voterTwo").value];
        await api("api/voters", {
          method: "POST",
          body: JSON.stringify({ voters }),
        });
        await loadState();
        setMessage("#setupMessage", "Voters saved.");
      } catch (error) {
        setMessage("#setupMessage", error.message, true);
      }
    });

    loadState().then(loadMovies);
  </script>
</body>
</html>
"""


def build_parser():
    parser = argparse.ArgumentParser(description="Run the Movie Night web prototype.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5001)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), MovieNightHandler)
    print(f"Movie Night web prototype running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Movie Night web prototype.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
