"""Create a consistent SQLite snapshot without copying a live WAL database."""
import argparse, os, sqlite3
from pathlib import Path
from server import DB
from database import is_postgres
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',required=True)
args=parser.parse_args()
if is_postgres(DB):parser.error('PostgreSQL requires pg_dump or your provider backup tools; this helper supports SQLite only. See deploy/RENDER_NEON.md.')
out=Path(args.output).resolve();source=Path(DB).resolve()
if not source.exists():parser.error('Source database does not exist. Set SSMS_DB to the server database.')
if out==source or out.exists():parser.error('Choose a new backup file; existing files are never overwritten.')
out.parent.mkdir(parents=True,exist_ok=True)
src=sqlite3.connect(f'{source.as_uri()}?mode=ro',uri=True);dest=sqlite3.connect(out)
try:src.backup(dest)
finally:dest.close();src.close()
print('Backup saved:',out)
