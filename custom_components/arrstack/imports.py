"""Shared, conservative import workflow for cards and HA automations."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
from typing import Any

from .api import ArrstackError, ArrstackConnectionError, ArrstackHTTPError, ArrstackAuthError
from .coordinator import is_import_problem, normalize_queue_record


def import_payload(candidates: list[dict[str, Any]], is_sonarr: bool, download_id: str) -> list[dict[str, Any]]:
    """Use only authoritative API assignments; never infer targets from names."""
    payload = []
    for candidate in candidates:
        parent = candidate.get('series') if is_sonarr else candidate.get('movie')
        if not parent or not parent.get('id'):
            continue
        item = {key: candidate.get(key) for key in ('path', 'folderName', 'quality', 'languages', 'releaseGroup')}
        item.update(downloadId=candidate.get('downloadId') or download_id, indexerFlags=candidate.get('indexerFlags', 0))
        if is_sonarr:
            episode_records = candidate.get('episodes') or []
            if not episode_records or any(not e.get('id') for e in episode_records):
                continue
            episodes = sorted(e['id'] for e in episode_records)
            if not episodes:
                continue
            item.update(seriesId=parent['id'], episodeIds=episodes)
        else:
            item['movieId'] = parent['id']
        payload.append(item)
    return payload


def _candidate(candidate: dict[str, Any], record: dict[str, Any], is_sonarr: bool) -> dict[str, Any]:
    """Normalize diagnostics and validate service/download/target ownership."""
    payload = import_payload([candidate], is_sonarr, record.get('downloadId') or '')
    reasons = [str(r.get('reason') or '') if isinstance(r, dict) else str(r) for r in candidate.get('rejections') or []]
    parent = candidate.get('series' if is_sonarr else 'movie') or {}
    queue_parent = record.get('series' if is_sonarr else 'movie') or {}
    valid = bool(payload and candidate.get('path') and not candidate.get('rejections'))
    if candidate.get('downloadId') and candidate['downloadId'] != record.get('downloadId'):
        valid = False
        reasons.append('Download-Zuordnung stimmt nicht überein')
    if queue_parent.get('id') and queue_parent['id'] != parent.get('id'):
        valid = False
        reasons.append('Serie/Film stimmt nicht überein')
    queue_episode = record.get('episode') or {}
    episode_ids = [e.get('id') for e in candidate.get('episodes') or []]
    if is_sonarr and queue_episode.get('id') and queue_episode['id'] not in episode_ids:
        valid = False
        reasons.append('Episode stimmt nicht überein')
    if not payload:
        reasons.append('Keine eindeutige Serie/Film-/Episodenzuordnung')
    identity_fields = ('path', 'seriesId', 'movieId', 'episodeIds')
    identity = json.dumps([{key: value for key, value in entry.items() if key in identity_fields} for entry in payload], sort_keys=True, ensure_ascii=False)
    candidate_id = hashlib.sha256(identity.encode()).hexdigest()[:24]
    path = candidate.get('path') or ''
    return {
        'candidate_id': candidate_id, 'valid': valid, 'path': path,
        'filename': path.replace('\\', '/').rsplit('/', 1)[-1],
        'name': candidate.get('name') or candidate.get('relativePath'),
        'size': candidate.get('size'),
        'quality': (candidate.get('quality') or {}).get('quality', {}).get('name'),
        'languages': [str(value.get('name') or '') if isinstance(value, dict) else str(value) for value in candidate.get('languages') or []],
        'release_group': candidate.get('releaseGroup'),
        'custom_formats': [str(value.get('name') or '') if isinstance(value, dict) else str(value) for value in candidate.get('customFormats') or []],
        'parent': parent.get('title'), 'episodes': episode_ids,
        'rejections': reasons,
    }


class ImportManager:
    """Fresh inspection before each write, serialized per configured instance."""

    def __init__(self, client: Any) -> None:
        self.client = client
        self._lock = asyncio.Lock()
        self._submitted: set[tuple[str, str]] = set()

    async def records(self) -> list[dict[str, Any]]:
        """Read every queue page; never claim the first page is the full queue."""
        data = await self.client.queue()
        records = list(data.get('records') or [])
        total = int(data.get('totalRecords') or len(records))
        page_size = int(data.get('pageSize') or 200)
        page = 2
        while len(records) < total:
            data = await self.client.queue(page=page, page_size=page_size)
            more = data.get('records') or []
            if not more:
                raise ArrstackError('Warteschlange unvollständig. Erneut aktualisieren.')
            records.extend(more)
            page += 1
        active = {r.get('downloadId') for r in records}
        self._submitted = {key for key in self._submitted if key[0] in active}
        return records

    async def _inspect_record(self, record: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        item = normalize_queue_record(record, self.client.is_sonarr)
        complete = str(record.get('status') or '').lower() == 'completed' and record.get('sizeleft') is not None and float(record['sizeleft']) == 0
        item.update(service=self.client.service, queue_item_id=record.get('id'), download_complete=complete,
                    import_state='not_applicable', candidate_count=None, candidates=[], last_error=None, last_checked=None,
                    can_auto_import=False)
        if not complete or not is_import_problem(record):
            return item, []
        item['last_checked'] = datetime.now(timezone.utc).isoformat()
        if not record.get('downloadId'):
            item.update(import_state='error', last_error='Download-ID fehlt. Zuordnung im Dienst prüfen.')
            return item, []
        try:
            raw = await self.client.manual_import_candidates(record['downloadId'])
            normalized = [_candidate(c, record, self.client.is_sonarr) for c in raw]
            # Duplicate rows do not prove a unique candidate; reject ambiguous IDs.
            ids = [c['candidate_id'] for c in normalized]
            for c in normalized:
                if ids.count(c['candidate_id']) > 1:
                    c['valid'] = False
                    c['rejections'].append('Mehrdeutige Kandidaten-ID')
            valid = [c for c in normalized if c['valid']]
            count = len(valid)
            item.update(candidates=normalized, candidate_count=count,
                        import_state='ready' if count == 1 else 'selection_required' if count > 1 else 'no_match',
                        can_auto_import=count == 1)
            return item, raw
        except ArrstackError:
            item.update(import_state='error', last_error='Kandidaten konnten nicht geprüft werden. Erneut versuchen.')
            return item, []

    async def refresh(self, queue_item_id: int | None = None) -> list[dict[str, Any]]:
        records = await self.records()
        if queue_item_id is not None:
            records = [r for r in records if r.get('id') == queue_item_id]
        return [(await self._inspect_record(record))[0] for record in records]

    async def inspect(self, queue_item_id: int) -> dict[str, Any]:
        items = await self.refresh(queue_item_id)
        if not items:
            raise ArrstackError('Queue-Eintrag fehlt. Warteschlange aktualisieren.')
        return items[0]

    async def import_item(self, queue_item_id: int, candidate_id: str | None = None, import_mode: str = 'auto') -> dict[str, Any]:
        async with self._lock:
            try:
                records = [r for r in await self.records() if r.get('id') == queue_item_id]
                if len(records) != 1:
                    raise ArrstackError('Queue-Eintrag fehlt oder ist mehrdeutig. Aktualisieren.')
                record = records[0]
                item, raw = await self._inspect_record(record)
                item['status'] = 'skipped'
                valid = [(c, source) for c, source in zip(item['candidates'], raw, strict=True) if c['valid']]
                chosen = [pair for pair in valid if pair[0]['candidate_id'] == candidate_id] if candidate_id else valid if len(valid) == 1 else []
                if len(chosen) != 1:
                    return item
                candidate, source = chosen[0]
                key = (record['downloadId'], candidate['candidate_id'])
                if key in self._submitted:
                    item['last_error'] = 'Import bereits übermittelt. Warteschlange aktualisieren.'
                    return item
                # Reserve before sending: a timeout may mean the service accepted
                # the import even when the response did not reach us.
                self._submitted.add(key)
                try:
                    await self.client.manual_import(import_payload([source], self.client.is_sonarr, record['downloadId']), import_mode)
                except ArrstackConnectionError:
                    # Keep reservation: the result of the write is uncertain.
                    raise
                except ArrstackAuthError:
                    self._submitted.discard(key)
                    raise
                except ArrstackHTTPError as err:
                    if 400 <= err.status < 500 and err.status != 408:
                        self._submitted.discard(key)
                        raise
                    raise ArrstackConnectionError("Importantwort ungewiss") from err
                except ArrstackError as err:
                    raise ArrstackConnectionError("Importantwort nicht lesbar") from err
                item.update(status='submitted', imported=1)
                return item
            except ArrstackConnectionError:
                return {'service': self.client.service, 'queue_item_id': queue_item_id, 'status': 'error', 'import_state': 'error', 'candidate_count': None, 'last_error': 'Verbindung unterbrochen. Importstatus ist ungewiss; Warteschlange im Dienst prüfen. Dieser Kandidat wird bis zum Entfernen aus der Queue nicht erneut importiert.'}
            except ArrstackError:
                return {'service': self.client.service, 'queue_item_id': queue_item_id, 'status': 'error', 'import_state': 'error', 'candidate_count': None, 'last_error': 'Import fehlgeschlagen. Warteschlange aktualisieren und erneut prüfen.'}

    async def import_selected(self, queue_item_ids: list[int]) -> list[dict[str, Any]]:
        return [await self.import_item(item_id) for item_id in dict.fromkeys(queue_item_ids)]

    async def import_ready(self) -> list[dict[str, Any]]:
        # import_item repeats all eligibility checks under the write lock.
        return await self.import_selected([r['id'] for r in await self.records()])
