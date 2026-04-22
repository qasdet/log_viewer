import re
from datetime import datetime
from typing import Optional


class LogEntry:
    def __init__(self, raw: str, timestamp: Optional[datetime] = None,
                 level: Optional[str] = None, message: str = ""):
        self.raw = raw
        self.timestamp = timestamp
        self.level = level
        self.message = message


class LogParser:
    # Common log format patterns
    PATTERNS = [
        # ISO format: 2024-01-15 10:30:45,123 INFO Message
        re.compile(r'^(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}[.,]\d{3})\s+(DEBUG|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL)\s+(.*)$'),
        # Common format: [2024-01-15 10:30:45] [INFO] Message
        re.compile(r'^\[?(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]\s*\[?(DEBUG|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL)\]?\s*(.*)$'),
        # Syslog format: Jan 15 10:30:45 hostname app[pid]: message
        re.compile(r'^([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+\S+\s+\S+:\s*(.*)$'),
        # Simple timestamp: 2024-01-15 10:30:45 LEVEL message
        re.compile(r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(DEBUG|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL)\s+(.*)$'),
        # Simple timestamp: 2024-01-15 10:30:45 message (no level)
        re.compile(r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(.*)$'),
    ]

    LEVEL_ALIASES = {
        'WARNING': 'WARN',
        'CRITICAL': 'ERROR',
        'FATAL': 'ERROR',
    }

    def __init__(self, path: str):
        self.path = path
        self.entries: list[LogEntry] = []
        self.available_levels: set[str] = set()
        self.available_dates: set[str] = set()
        self._parse()

    def _normalize_level(self, level: str) -> str:
        level = level.upper()
        return self.LEVEL_ALIASES.get(level, level)

    def _parse_timestamp(self, ts_str: str) -> Optional[datetime]:
        for fmt in ('%Y-%m-%d %H:%M:%S,%f', '%Y-%m-%d %H:%M:%S.%f',
                    '%Y-%m-%dT%H:%M:%S,%f', '%Y-%m-%dT%H:%M:%S.%f',
                    '%Y-%m-%d %H:%M:%S'):
            try:
                ts_str_clean = ts_str.replace(',', '.').replace('T', ' ')
                return datetime.strptime(ts_str_clean.rstrip('.'), fmt)
            except ValueError:
                continue
        return None

    def _parse(self):
        for line in open(self.path, encoding='utf-8', errors='replace'):
            line = line.rstrip('\n\r')
            if not line.strip():
                continue

            entry = LogEntry(raw=line)
            matched = False

            for pattern in self.PATTERNS:
                m = pattern.match(line)
                if m:
                    groups = m.groups()
                    if len(groups) >= 3:
                        ts_str, level, msg = groups[0], groups[1], groups[2]
                    elif len(groups) == 2:
                        ts_str, msg = groups[0], groups[1]
                        level = None
                    else:
                        continue

                    entry.timestamp = self._parse_timestamp(ts_str)
                    entry.level = self._normalize_level(level) if level else None
                    entry.message = msg if msg else line
                    matched = True
                    break

            if not matched:
                entry.message = line
                # Try to extract timestamp from line start
                ts_match = re.match(r'^(\d{4}-\d{2}-\d{2})', line)
                if ts_match:
                    entry.timestamp = datetime.strptime(ts_match.group(1), '%Y-%m-%d')

            if entry.timestamp:
                self.available_dates.add(entry.timestamp.strftime('%Y-%m-%d'))
            if entry.level:
                self.available_levels.add(entry.level)

            self.entries.append(entry)

    def filter_entries(self,
                       date_from: Optional[str] = None,
                       date_to: Optional[str] = None,
                       levels: Optional[set[str]] = None,
                       search_text: Optional[str] = None) -> list[LogEntry]:
        result = []
        for entry in self.entries:
            if date_from and entry.timestamp:
                if entry.timestamp.strftime('%Y-%m-%d') < date_from:
                    continue
            if date_to and entry.timestamp:
                if entry.timestamp.strftime('%Y-%m-%d') > date_to:
                    continue
            if levels and entry.level and entry.level not in levels:
                continue
            if search_text:
                if search_text.lower() not in entry.raw.lower():
                    continue
            result.append(entry)
        return result
