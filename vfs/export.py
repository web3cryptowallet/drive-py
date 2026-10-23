"""Export catalogs as importable LiveLog records and lossless JSON lines."""
# IMPORT EXPORT DEPENDENCIES [
import json
from pathlib import Path
import tempfile
import os
# IMPORT EXPORT DEPENDENCIES ]
# EXPORT LIVELOG FOR THE EXPORT WORKFLOW [
def export_livelog(db, directory):
    destination = Path(directory).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Refuse to mix a snapshot with previous imports or overwrite unrelated files.
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError(f'Export directory must be empty: {destination}')
    with tempfile.TemporaryDirectory(prefix='.livelog-export-', dir=destination.parent) as temporary:
        staged = Path(temporary) / 'snapshot'
        staged.mkdir()
        _write_snapshot(db, staged)
        if destination.exists():
            destination.rmdir()
        os.replace(staged, destination)
# EXPORT LIVELOG FOR THE EXPORT WORKFLOW ]
# WRITE SNAPSHOT FOR THE EXPORT WORKFLOW [
def _write_snapshot(db, destination):
    stores = getattr(db, 'stores', {'': db})
    routes = getattr(db, 'routes', {})
    manifest = []
    # One read transaction gives a consistent snapshot across attached databases.
    with db.conn:
        db.conn.execute('BEGIN')
        for index, (prefix, store) in enumerate(stores.items()):
            folder = destination / f'{index:03d}'
            folder.mkdir()
            manifest.append({'prefix': prefix or '/',
                             'database': str(Path(routes.get(prefix, db.db_path)).resolve()),
                             'directory': folder.name})
            with (folder / 'llog-llogfiles.sh').open('w') as log, (folder / 'nodes.jsonl').open('w') as nodes:
                log.write('# files [\n')
                for row in store.conn.execute('SELECT * FROM nodes ORDER BY id'):
                    nodes.write(json.dumps(dict(row), ensure_ascii=True) + '\n')
                    if row['is_dir']:
                        continue
                    info = json.loads(row['info'])
                    hashinfo = info.get('hashinfo')
                    if not hashinfo:
                        continue
                    digest, size = hashinfo.rsplit(':', 1)
                    algorithm, value = digest.split(':', 1) if ':' in digest else ('MD5', digest)
                    path = info.get('path', row['id'])
                    if '\n' in path or '\r' in path:
                        raise ValueError('LiveLog cannot represent paths containing line breaks')
                    log.write(f'{algorithm} {value} "{path}" {size}\n')
                log.write('# files ]\n')
            with (folder / 'hashes.jsonl').open('w') as hashes:
                for row in store.conn.execute('SELECT * FROM hashes'):
                    hashes.write(json.dumps(dict(row), ensure_ascii=True) + '\n')
        # Scanner and thumbnail metadata stay in the coordinator; preserve all tables.
        with (destination / 'coordinator.sql').open('w') as snapshot:
            for line in db.conn.iterdump():
                snapshot.write(line + '\n')
    (destination / 'db-paths.json').write_text(json.dumps(manifest, indent=2) + '\n')
# WRITE SNAPSHOT FOR THE EXPORT WORKFLOW ]
