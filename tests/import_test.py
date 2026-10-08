"""Transport and safety regression tests, using local fixtures only."""
import asyncio
import copy
from urllib.parse import quote
from aiohttp import ClientSession, web
from smoke_test import make_client, SONARR_QUEUE, SONARR_CANDIDATES_SAFE
from arrstack.api import SeerrClient, ArrstackError, ArrstackConnectionError, ArrstackHTTPError

async def main():
    seen = []
    async def search(request):
        seen.append(request.raw_path)
        return web.json_response({'query': request.query['query']})
    app = web.Application()
    app.router.add_get('/api/v1/search', search)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    async with ClientSession() as session:
        client = make_client(SeerrClient, session, f'http://127.0.0.1:{runner.addresses[0][1]}', 'test-key')
        for query in ['a b', '&', '+', '/', '?', '#', '%', 'ä ö ü ß', "O'Brian", 'a:b', '(a)', '東京 🎬', 'already%20literal']:
            result = await client.search(query)
            assert result['query'] == query
            assert seen[-1] == '/api/v1/search?query=' + quote(query, safe='') + '&page=1', seen[-1]
    await runner.cleanup()
    from arrstack.coordinator import classify_candidates
    assert not classify_candidates(SONARR_CANDIDATES_SAFE + SONARR_CANDIDATES_SAFE)["can_auto_import"]
    from arrstack.imports import ImportManager
    class Client:
        is_sonarr = True
        service = 'sonarr'
        def __init__(self):
            self.records = [copy.deepcopy(SONARR_QUEUE['records'][1])]
            self.candidates = copy.deepcopy(SONARR_CANDIDATES_SAFE)
            self.calls = []
            self.writes = []
            self.failure = False
            self.candidates[0]['downloadId'] = 'def'
        async def queue(self, **kw):
            return {'records': self.records, 'totalRecords': len(self.records)}
        async def manual_import_candidates(self, download_id):
            self.calls.append(download_id)
            if self.failure: raise ArrstackError('fixture failure')
            return copy.deepcopy(self.candidates)
        async def manual_import(self, payload, mode):
            self.writes.append(payload)
            return {'id':101,'name':'ManualImport','status':'queued'}
    client = Client()
    manager = ImportManager(client)
    for progress in [20, 50, 99]:
        client.records[0]['sizeleft'] = 2000 * (100-progress)/100
        item = await manager.inspect(2)
        assert item['import_state'] == 'not_applicable'
        assert item['candidate_count'] is None
    assert not client.calls
    client.records[0]['sizeleft'] = 0
    client.records[0]['trackedDownloadState'] = 'imported'
    assert (await manager.inspect(2))['import_state'] == 'not_applicable'
    client.records[0]['trackedDownloadState'] = 'importPending'
    item = await manager.inspect(2)
    assert item['download_complete'] and item['candidate_count'] == 1 and item['import_state'] == 'ready'
    assert item['candidates'][0]['languages'] == ['English']
    client.candidates[0]['customFormats'] = [{'id':1,'name':'Custom format'}]
    assert (await manager.inspect(2))['candidates'][0]['custom_formats'] == ['Custom format']
    candidate_id = item['candidates'][0]['candidate_id']
    client.candidates = []
    assert (await manager.inspect(2))['import_state'] == 'no_match'
    assert (await manager.import_item(2))['status'] == 'skipped'
    client.candidates = copy.deepcopy(SONARR_CANDIDATES_SAFE) + copy.deepcopy(SONARR_CANDIDATES_SAFE)
    client.candidates[0]['downloadId'] = client.candidates[1]['downloadId'] = 'def'
    client.candidates[1]['path'] += '.other.mkv'
    item = await manager.inspect(2)
    assert item['candidate_count'] == 2 and item['import_state'] == 'selection_required'
    assert (await manager.import_item(2))['status'] == 'skipped'
    assert (await manager.import_item(2, item['candidates'][1]['candidate_id']))['status'] == 'submitted'
    assert len(client.writes[-1]) == 1
    client.candidates = copy.deepcopy(SONARR_CANDIDATES_SAFE)
    client.candidates[0]['downloadId'] = 'WRONG'
    assert (await manager.inspect(2))['candidate_count'] == 0
    client.candidates[0]['downloadId'] = 'def'
    client.candidates[0]['rejections'] = [{'reason': 'new unknown restriction'}]
    assert (await manager.inspect(2))['candidate_count'] == 0
    client.candidates[0]['rejections'] = []
    client.failure = True
    assert (await manager.inspect(2))['import_state'] == 'error'
    client.failure = False
    client.records += [{**copy.deepcopy(client.records[0]), 'id': 3, 'downloadId': 'multiple'}, {**copy.deepcopy(client.records[0]), 'id': 4, 'sizeleft': 100}]
    results = await manager.import_selected([2,3,4,999,2])
    assert [r['status'] for r in results] == ['submitted','skipped','skipped','error']
    assert len(client.writes) == 2
    client.records.append({**copy.deepcopy(client.records[0]), 'id': 5})
    assert (await manager.import_item(5))['status'] == 'skipped'
    assert len(client.writes) == 2
    assert (await manager.import_item(2,'stale'))['status'] == 'skipped'
    client.records[0]['sizeleft'] = 100
    assert (await manager.import_item(2,candidate_id))['status'] == 'skipped'
    # Definitive rejection is retryable; timeout has an uncertain outcome.
    client.records[0]['sizeleft'] = 0
    for error, retry in [(ArrstackHTTPError(400,'HTTP 400 fixture'), True), (ArrstackHTTPError(500,'HTTP 500 fixture'), False), (ArrstackError('unreadable response'), False), (ArrstackConnectionError('timeout fixture'), False)]:
        fresh = ImportManager(client)
        original = client.manual_import
        async def fail(payload, mode): raise error
        client.manual_import = fail
        failed = await fresh.import_item(2)
        assert failed['status'] == 'error'
        assert failed['last_error_code'] in ('request_rejected','uncertain_submission')
        assert isinstance(failed['last_error_details'], dict)
        assert 'fixture' not in str(failed['last_error_details'])
        client.manual_import = original
        assert (await fresh.import_item(2))['status'] == ('submitted' if retry else 'skipped')
    # Radarr ownership and missing target are equally strict.
    client.is_sonarr = False
    client.service = 'radarr'
    client.candidates = [{'path':'/downloads/movie.mkv','movie':{'id':10,'title':'Film'},'downloadId':'def','quality':{},'rejections':[]}]
    client.records = [{**client.records[0], 'movie':{'id':10}}]
    fresh = ImportManager(client)
    assert (await fresh.inspect(2))['import_state'] == 'ready'
    assert (await fresh.import_item(2))['status'] == 'submitted'
    assert client.writes[-1][0]['movieId'] == 10
    client.candidates[0]['movie']['id'] = 11
    assert (await fresh.inspect(2))['import_state'] == 'no_match'
    client.candidates[0]['movie'] = {}
    assert (await fresh.inspect(2))['candidate_count'] == 0
    # Real two-page collection feeds the safe bulk path.
    client.candidates[0]['movie'] = {'id':10}
    client.records.append({**copy.deepcopy(client.records[0]), 'id':6})
    async def paged(page=1, page_size=1):
        return {'records':client.records[page-1:page], 'totalRecords':2,'pageSize':1}
    client.queue = paged
    fresh = ImportManager(client)
    assert len(await fresh.refresh()) == 2
    results = await fresh.import_ready()
    assert [r['status'] for r in results] == ['submitted','skipped']
    # Concurrent submissions of the same file also issue one backend write.
    fresh = ImportManager(client)
    before = len(client.writes)
    results = await asyncio.gather(fresh.import_item(2), fresh.import_item(6))
    assert sorted(r['status'] for r in results) == ['skipped','submitted']
    assert len(client.writes) == before + 1
    print('Encoding cases and import safety regression tests passed')

asyncio.run(main())
