# Changelog

All notable changes to Movie Night will be documented in this file.

## Unreleased

### Added
- Added `data/seed-movies.csv` as a tracked, editable CSV seed list for fresh installs.
- Added `create_database.py` to build a local SQLite `pm.db` from the seed CSV or a compatible custom CSV.
- Added first-run database setup that offers to create `pm.db` from the seed CSV when the movie table is missing.
- Added `movie-night.py` as the user-facing command-line entry point.
- Added `movie_night.py` as the importable application module.
- Added a local `AGENTS.md` context file for future assistant sessions.

### Changed
- Replaced the ignored local movie list workflow with the tracked seed CSV as the source for new databases.
- Updated the seed list by removing `Suspiria` and adding `RoboCop` while keeping movie IDs continuous.
- Updated tests to create temporary databases from the seed CSV instead of relying on the ignored local `pm.db`.
- Kept `main.py` as a compatibility wrapper so existing imports and old commands continue to work.
- Updated README, help text, and subprocess tests to use `movie-night.py`.
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
