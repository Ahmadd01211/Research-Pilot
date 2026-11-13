#!/bin/sh
# Back up the database and uploaded PDFs from the production stack (docs/DEPLOYMENT.md).
# Reads application data only; prunes nothing but its own older backup files (keeps 7 of each).
set -eu
cd "$(dirname "$0")/.."
dir="${BACKUP_DIR:-$HOME/researchpilot-backups}"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
compose="docker compose -f compose.yaml -f compose.prod.yaml"
mkdir -p "$dir"
$compose exec -T db pg_dump -U rp -d rp_greenfield --format=custom > "$dir/db-$stamp.dump.partial"
mv "$dir/db-$stamp.dump.partial" "$dir/db-$stamp.dump"
$compose exec -T api tar -czf - -C /var/lib/researchpilot . > "$dir/papers-$stamp.tar.gz.partial"
mv "$dir/papers-$stamp.tar.gz.partial" "$dir/papers-$stamp.tar.gz"
for pattern in 'db-*.dump' 'papers-*.tar.gz'; do
  find "$dir" -maxdepth 1 -name "$pattern" -type f | sort -r | tail -n +8 | xargs -r rm --
done
echo "Backup written to $dir ($stamp)"
