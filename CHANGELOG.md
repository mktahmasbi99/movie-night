# Changelog

All notable changes to Movie Night will be documented in this file.

## Unreleased

### Added
- Added a Rewatch column to the browser movie list with status-style Yes/No badges and blank display for unset values.
- Fixed browser API calls so the app works correctly behind code-server proxy URLs.
- Added `app.py` as a dependency-free browser prototype for picking movies, saving voters, voting, and viewing filtered movie lists.
- Added `data/seed-movies.csv` as a tracked, editable CSV seed list for fresh installs.
- Added `create_database.py` to build a local SQLite `pm.db` from the seed CSV or a compatible custom CSV.
- Added first-run database setup that offers to create `pm.db` from the seed CSV when the movie table is missing.
- Consolidated the command-line entry point and importable application module into `movie_night.py`.
- Added a local `AGENTS.md` context file for future assistant sessions.

### Changed
- Added regression coverage to ensure existing `pm.db` files are used as-is without seed import, metadata sync, or schema changes.
- Updated README with instructions for running the browser prototype on a local or forwarded port.
- Replaced the ignored local movie list workflow with the tracked seed CSV as the source for new databases.
- Updated the seed list by removing `Suspiria` and adding `RoboCop` while keeping movie IDs continuous.
- Updated tests to create temporary databases from the seed CSV instead of relying on the ignored local `pm.db`.
- Removed the old compatibility wrappers `main.py` and `movie-night.py`.
- Updated README, help text, and subprocess tests to use `movie_night.py`.
- Stopped tracking local helper files under `files-to-ignore/` while keeping them available locally.

## Current CLI Version

### Added
- Added a two-person voting flow for randomly selected unwatched movies.
- Added first-run voter setup with persisted names in SQLite.
- Added commands to list watched and unwatched movies.
- Added automatic movie status updates: watched if either voter says yes, skipped if both say no.
- Added SQLite constraints for movie status, rewatch flag, and voter names.
- Added unit tests for voting behavior, voter setup, database constraints, and command-line handling.

### Changed
- Made database and help-file paths independent of the current working directory.
- Cleaned up command handling and README usage examples.

## Initial Version

### Added
- Created the initial command-line Movie Night project.
- Added the initial movie database workflow and helper scripts used during local setup.
