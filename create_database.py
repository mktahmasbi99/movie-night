import argparse
from pathlib import Path

from movie_night import DEFAULT_DB_PATH, DEFAULT_SEED_PATH, create_database_from_csv


def build_parser():
    parser = argparse.ArgumentParser(
        description="Create a Movie Night SQLite database from a seed CSV."
    )
    parser.add_argument(
        "--csv",
        default=DEFAULT_SEED_PATH,
        type=Path,
        help="CSV file with id,title,year,director headers.",
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_DB_PATH,
        type=Path,
        help="SQLite database path to create.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Replace film rows if the database already exists.",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.db.exists() and not args.replace:
        print(f"{args.db} already exists. Use --replace to rebuild it from CSV.")
        return 1

    movie_count = create_database_from_csv(args.db, args.csv)
    print(f"Created {args.db} with {movie_count} movies from {args.csv}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
