"""Actual HTTP contracts from Sonarr 4.0.20.3014 / Radarr 6.4.4.10685.

Fixtures expose /manualimport as reprocessing, not a fake import endpoint.
All writes go only to this disposable in-process HTTP server.
"""
import asyncio
from aiohttp import ClientSession, web
from smoke_test import make_client
from arrstack.api import ArrClient, ArrstackError
from arrstack.coordinator import normalize_queue_record
from arrstack.imports import ImportManager

async def main():
    seen = []
    current_service = 'sonarr'
    command_response = {'id': 101, 'name': 'ManualImport', 'status': 'queued'}
    async def command(request):
        seen.append((request.path, await request.json()))
        return web.json_response(command_response)
    async def reprocess(request):
        seen.append((request.path, await request.json()))
        return web.json_response([])
    async def queue(request):
        parent_key = 'series' if current_service == 'sonarr' else 'movie'
        return web.json_response({'records':[{'id':1,'downloadId':'fixture','status':'completed','size':100,'sizeleft':0,'trackedDownloadStatus':'warning','trackedDownloadState':'importBlocked',parent_key:{'id':10},'episode':{'id':22}}],'totalRecords':1})
    async def candidates(request):
        parent_key = 'series' if current_service == 'sonarr' else 'movie'
        return web.json_response([{'path':'/downloads/fixture.mkv','downloadId':'fixture',parent_key:{'id':10},'episodes':[{'id':22}], 'quality':{'quality':{'id':7}},'languages':[{'id':1,'name':'English'}],'rejections':[]}])
    app = web.Application()
    app.router.add_get('/api/v3/queue', queue)
    app.router.add_get('/api/v3/manualimport', candidates)
    app.router.add_post('/api/v3/command', command)
    app.router.add_post('/api/v3/manualimport', reprocess)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    try:
        async with ClientSession() as session:
            base = f'http://127.0.0.1:{runner.addresses[0][1]}'
            for service, target in [('sonarr', {'seriesId': 10, 'episodeIds': [22]}), ('radarr', {'movieId': 11})]:
                current_service = service
                client = make_client(ArrClient, session, base, 'test-key', service)
                files = [{'path': '/downloads/fixture.mkv', **target, 'quality': {'quality': {'id': 7}}, 'languages': [{'id': 1, 'name': 'English'}]}]
                result = await client.manual_import(files, 'copy')
                assert seen[-1][0] == '/api/v3/command', 'POST /manualimport only reprocesses; it never imports files'
                assert seen[-1][1] == {'name':'ManualImport', 'files':files, 'importMode':'copy'}
                assert result['id'] == 101
                managed = await ImportManager(client).import_item(1)
                assert managed['status'] == 'submitted' and managed['command_id'] == 101
                for invalid in [None, [], {}, {'id':True,'name':'ManualImport'}, {'id':0,'name':'ManualImport'}, {'id':101,'name':'Other'}, {'id':101,'name':'ManualImport','status':'failed'}, {'id':101,'name':'ManualImport','status':'aborted'}]:
                    command_response = invalid
                    try:
                        await client.manual_import(files)
                    except ArrstackError:
                        pass
                    else:
                        raise AssertionError(f'{service} must not claim invalid command response is submitted')
                    managed = await ImportManager(client).import_item(1)
                    assert managed['status'] == 'error' and managed['last_error_code'] == 'invalid_command_response'
                command_response = {'id':101,'name':'ManualImport','status':'queued'}
    finally:
        await runner.cleanup()
    record = {'id':1, 'episode':{'title':'Episode','airDate':'2026-01-02'}, 'languages':[{'id':1,'name':'English'}], 'quality':{'quality':{'name':'WEBDL-1080p'}}, 'customFormats':[{'id':1,'name':'Format'}], 'customFormatScore':0, 'outputPath':'/downloads/fixture'}
    item = normalize_queue_record(record, True)
    assert {key:item[key] for key in ['episode_title','episode_air_date','languages','quality','custom_formats','custom_format_score','output_path']} == {'episode_title':'Episode','episode_air_date':'2026-01-02','languages':['English'],'quality':'WEBDL-1080p','custom_formats':['Format'],'custom_format_score':0,'output_path':'/downloads/fixture'}
    empty = normalize_queue_record({}, True)
    assert all(empty[key] is None for key in ['episode_title','episode_air_date','languages','quality','custom_formats','custom_format_score','output_path'])
    malformed = normalize_queue_record({'languages':'unexpected','quality':[], 'customFormats':{'bad':'value'},'customFormatScore':'invalid','episode':'unexpected'},True)
    assert all(malformed[key] is None for key in ['episode_title','episode_air_date','languages','quality','custom_formats','custom_format_score'])
    print('Sonarr/Radarr ManualImport HTTP contract, response validation and optional queue fields passed')

asyncio.run(main())
