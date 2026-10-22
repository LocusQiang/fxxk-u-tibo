"""Read-only local journal summaries. No chat content or network access."""
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import time


def summarize(path, days=30, now=None, tz=None):
    if days not in (7, 30, 90):
        raise ValueError('Choose 7, 30, or 90 days')
    today = datetime.fromtimestamp(time.time() if now is None else now, tz).date()
    daily = {today - timedelta(days=i): {'sent': set(), 'unknown': set(), 'chats': set()}
             for i in reversed(range(days))}
    confirmed, latest, seen, malformed = [], {}, set(), 0
    path = Path(path)
    if path.exists():
        with path.open(encoding='utf-8-sig', errors='replace') as stream:
            for line in stream:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    if (not isinstance(row, dict) or not isinstance(row.get('key'), str)
                            or not row['key'] or not isinstance(row.get('status'), str)
                            or isinstance(row.get('at'), bool)
                            or not isinstance(row.get('at'), (int, float))
                            or not math.isfinite(row['at'])
                            or (row.get('message_id') is not None and not isinstance(row['message_id'], str))):
                        raise ValueError('Invalid journal row')
                    day = datetime.fromtimestamp(row['at'], tz).date()
                except (ValueError, TypeError, KeyError, OverflowError, OSError):
                    malformed += 1
                    continue
                latest[row['key']] = row
                if row['status'] == 'sent':
                    identity = row.get('message_id') or row['key']
                    if identity not in seen:
                        seen.add(identity)
                        confirmed.append(row)
                    if day in daily:
                        daily[day]['sent'].add(identity)
                        daily[day]['chats'].add(row['key'].split(':', 1)[0])
    sent_keys = {row['key'] for row in confirmed}
    unresolved = [row for key, row in latest.items()
                  if key not in sent_keys and row['status'] in ('sending', 'unknown')]
    for row in unresolved:
        day = datetime.fromtimestamp(row['at'], tz).date()
        if day in daily:
            daily[day]['unknown'].add(row['key'])
    rows = [{'date': day.isoformat(), **{name: len(values) for name, values in item.items()}}
            for day, item in daily.items()]
    return {'days': rows, 'today': rows[-1]['sent'], 'total': len(seen),
            'period': sum(row['sent'] for row in rows), 'unknown': len(unresolved),
            'malformed': malformed, 'active_days': sum(row['sent'] > 0 for row in rows)}
