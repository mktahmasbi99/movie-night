# Changelog

All notable changes to Movie Night will be documented in this file.

## Unreleased

### Added
- Added generated cinema-themed header artwork to the browser UI.
- Added confirmed edit and delete controls plus a simpler unconfirmed add flow for movie entries in the browser movie list.
- Added a Rewatch-Worthy movie-list column and filter with status-style Yes/No badges and blank display for unset values.
- Fixed browser API calls so the app works correctly behind code-server proxy URLs.
- Added `app.py` as the dependency-free browser UI for picking movies, saving voters, voting, managing movie entries, and viewing filtered movie lists.
- Added `data/seed-movies.csv` as a tracked, editable CSV seed list for fresh installs.
- Added `create_database.py` to build a local SQLite `pm.db` from the seed CSV or a compatible custom CSV.
- Added first-run database setup that offers to create `pm.db` from the seed CSV when the movie table is missing.
- Consolidated the command-line entry point and importable application module into `movie_night.py`.
- Added a local `AGENTS.md` context file for future assistant sessions.

### Changed
- Reworked the browser UI header into a full-width hero image with translucent tabs integrated at the bottom.
- Reworked README to present Movie Night as a browser-based app while keeping terminal commands documented as a secondary interface.
- Moved Pick Movie into the Tonight tab so it only appears with the voting workflow.
- Added regression coverage to ensure existing `pm.db` files are used as-is without seed import, metadata sync, or schema changes.
- Updated README with instructions for running the browser UI on a local or forwarded port.
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
