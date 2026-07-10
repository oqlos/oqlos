#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8202}"
FILE="panel-task-crud-$(date +%s).oql"
CONTENT=$'VERSION: 4\nSCENARIO: task-crud\nGOAL:\n  SET WAIT \'1 s\'\n'

echo "→ POST $FILE"
curl -fsS -X POST "$BASE_URL/api/v1/editor/file/$FILE" \
  -H "Content-Type: application/json" \
  -d "{\"path\":\"$FILE\",\"content\":$(python3 -c "import json,sys; print(json.dumps(sys.stdin.read()))" <<<"$CONTENT")}" \
  >/dev/null

echo "→ GET $FILE"
curl -fsS "$BASE_URL/api/v1/editor/file/$FILE" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'VERSION: 4' in d.get('content',''), d"

echo "→ DELETE $FILE"
curl -fsS -X DELETE "$BASE_URL/api/v1/editor/file/$FILE" >/dev/null

echo "→ GET missing"
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/editor/file/$FILE")
test "$code" = "404"

echo "✅ panel editor CRUD smoke passed ($BASE_URL)"
