import json
import asyncio
import importlib
import types
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from PIL import Image, PngImagePlugin

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from image_prompt_library.extractor import Resolver, extract, read_metadata
from image_prompt_library.library import Library
from image_prompt_library.server import make_server
from image_prompt_library.launch import ensure_started


def node(kind, **inputs):
    return {"class_type": kind, "inputs": inputs}


def graph(text="a quiet mountain", negative="blur"):
    return {"1": node("CLIPTextEncode", text=text), "2": node("CLIPTextEncode", text=negative),
            "3": node("KSampler", positive=["1", 0], negative=["2", 0], seed=12),
            "4": node("VAEDecode", samples=["3", 0]), "5": node("SaveImage", images=["4", 0]),
            "unused": node("CLIPTextEncode", text="unused text")}


def png(path, prompt=None):
    info = PngImagePlugin.PngInfo()
    if prompt:
        info.add_text("prompt", json.dumps(prompt))
    Image.new("RGB", (24, 32), "#408060").save(path, pnginfo=info)


@pytest.mark.parametrize("saver", ["SaveImage", "SaveImageAdvanced"])
def test_direct_prompt_ignores_unused_and_negative(saver):
    stored = graph()
    stored["5"]["class_type"] = saver
    result = extract({"prompt": stored})
    assert result["positive"] == "a quiet mountain"
    assert result["issues"] == []
    assert result["stages"][0]["negative"] == "blur"


def test_join_and_conditioning_semantics():
    g = graph(["join", 0])
    g["join"] = node("JoinStrings", string1="red", string2="bird", delimiter=", ")
    g["other"] = node("CLIPTextEncode", text="forest")
    g["combined"] = node("ConditioningCombine", conditioning_1=["1", 0], conditioning_2=["other", 0])
    g["concat"] = node("ConditioningConcat", conditioning_to=["combined", 0], conditioning_from=["combined", 0])
    g["3"]["inputs"]["positive"] = ["concat", 0]
    result = extract({"prompt": g})
    assert not result["issues"]
    assert result["stages"][0]["branches"] == ["red, bird\nred, bird", "forest\nred, bird"]
    assert any(op["type"] == "ConditioningConcat" for op in result["stages"][0]["operations"])


def test_multi_join_and_switch_relay():
    g = graph(["relay", 0])
    g["relay"] = node("KVGC_GetRelay", value=["switch", 0])
    g["switch"] = node("LazySwitchKJ", switch=True, on_true=["multi", 0], on_false=["unknown", 0])
    g["multi"] = node("JoinStringMulti", inputcount=3, string_1="", string_2="cat", string_3="", delimiter="|", return_list=False)
    assert extract({"prompt": g})["positive"] == "|cat"
    assert not extract({"prompt": g})["issues"]
    g["multi"]["inputs"]["return_list"] = True
    assert extract({"prompt": g})["issues"]


def test_native_text_concatenation():
    g = graph(["join", 0])
    g["join"] = node("StringConcatenate", string_a="a", string_b="b", delimiter=" / ")
    assert extract({"prompt": g})["positive"] == "a / b"
    assert not extract({"prompt": g})["issues"]


def test_unknown_generator_retains_recoverable_prompt():
    g = {"api": node("CustomImageGenerator", prompt="stored prompt"), "save": node("SaveImage", images=["api", 0])}
    result = extract({"prompt": g})
    assert result["positive"] == "stored prompt"
    assert any("unsupported generation stage" in issue for issue in result["issues"])


@pytest.mark.parametrize("replacement", [node("UnknownText", text="fragment"), node("Reroute", value=["1", 0])])
def test_unsupported_and_cycles_need_review(replacement):
    g = graph()
    g["1"] = replacement
    assert extract({"prompt": g})["issues"]


def test_multistage_and_multiple_outputs_are_not_silently_flattened():
    g = graph()
    g["refine"] = node("KSampler", positive=["unused", 0], negative=["2", 0], latent_image=["3", 0])
    g["4"]["inputs"]["samples"] = ["refine", 0]
    result = extract({"prompt": g})
    assert len(result["stages"]) == 2
    assert any("stages" in issue for issue in result["issues"])
    g["save2"] = node("SaveImage", images=["4", 0])
    assert any("Multiple image outputs" in issue for issue in extract({"prompt": g})["issues"])


def test_visual_workflow_recovers_fragments_but_requires_review():
    workflow = {"nodes": [{"id": 1, "type": "CLIPTextEncode", "widgets_values": ["visual prompt"]},
                           {"id": 3, "type": "KSampler", "inputs": [{"name": "positive", "link": 1}]},
                           {"id": 5, "type": "SaveImage", "inputs": [{"name": "images", "link": 2}]}],
                "links": [[1, 1, 0, 3, 0, "CONDITIONING"], [2, 3, 0, 5, 0, "IMAGE"]]}
    result = extract({"workflow": workflow})
    assert result["positive"] == "visual prompt"
    assert any("visual workflow" in issue for issue in result["issues"])


@pytest.mark.parametrize("extension", ["png", "jpg", "webp"])
def test_image_metadata_formats(tmp_path, extension):
    path = tmp_path / f"image.{extension}"
    if extension == "png":
        png(path, graph())
    else:
        exif = Image.Exif()
        exif[0x0110] = "prompt:" + json.dumps(graph())
        exif[0x010f] = "workflow:" + json.dumps({"nodes": []})
        Image.new("RGB", (16, 16)).save(path, exif=exif)
    assert extract(read_metadata(path))["positive"] == "a quiet mountain"


def test_persistence_grouping_search_correction_and_rescan(tmp_path):
    library = Library(tmp_path / "db")
    a, b, c = (tmp_path / name for name in ("a.png", "b.png", "c.png"))
    png(a, graph(" mountain\r\nview ", "bad")); png(b, graph("mountain\nview", "different"))
    unresolved = graph(); unresolved['1'] = node('UnknownText', text='fragment'); png(c, unresolved)
    assert library.index(a) and library.index(b) and library.index(c)
    assert not library.index(a)
    listing = library.listing()
    assert listing["total"] == 1 and listing["items"][0]["count"] == 2
    assert library.listing("b.png")["items"][0]["count"] == 2
    review = library.listing(review=True)["items"][0]
    library.correct(review["id"], "mountain\nview")
    assert Library(tmp_path / "db").listing()["items"][0]["count"] == 3
    assert not library.index(c)
    assert library.get(review["id"])["correction"] == "mountain\nview"
    b.unlink()
    assert any(item["missing"] for item in library.images(listing["items"][0]["group_id"], 0)["items"])
    png(a, graph("changed prompt"))
    assert library.index(a)
    assert library.listing()["total"] == 2


def test_scan_corrupt_and_cancel(tmp_path):
    library = Library(tmp_path / "db")
    (tmp_path / "broken.png").write_bytes(b"not an image")
    png(tmp_path / "good.png", graph())
    library.scan(tmp_path, True)
    assert library.listing()["total"] == 1
    assert library.listing(review=True)["total"] == 1
    library.cancel.set()
    library.scan(tmp_path, True)
    assert library.snapshot()["state"] == "cancelled"


@pytest.mark.parametrize('kind', ['TextGenerateV2', 'TextGenerate', 'CustomPromptEnhancer'])
def test_enhancer_instructions_are_not_prompts(kind):
    g = graph(['enhance', 0])
    g['enhance'] = node(kind, prompt=['source', 0], system_prompt=['instructions', 0], instruction_prompt=['instructions', 0])
    g['source'] = node('PrimitiveString', value='a mountain lake')
    g['instructions'] = node('PrimitiveString', value='SYSTEM: rewrite the text into a detailed prompt')
    result = extract({'prompt': g})
    assert result['positive'] == 'a mountain lake'
    assert 'SYSTEM:' not in json.dumps(result)
    assert any('output is not stored' in issue for issue in result['issues'])
    assert len(result['stages']) == 1


@pytest.mark.parametrize('enabled', [False, True])
def test_minimax_edit_task_template_and_switch(enabled):
    g = graph()
    g['1'] = node('MiniMaxH3ImageConditioning', prompt=['preview', 0], clip=['clip', 0],
                  **{'images.image_0': ['image', 0]})
    g['2'] = node('ConditioningZeroOut', conditioning=['1', 0])
    g.update({
        'preview': node('PreviewAny', source=['switch', 0]),
        'switch': node('ComfySwitchNode', switch=['enabled', 0], on_false=['assembled', 0], on_true=['json', 0]),
        'enabled': node('PrimitiveBoolean', value=enabled),
        'json': node('JsonExtractString', json_string=['enhancer', 0], key='expanded_caption'),
        'enhancer': node('TextGenerateV2', prompt=['replace', 0], system_prompt='SYSTEM INSTRUCTIONS'),
        'replace': node('StringReplace', string=['task', 0], find='{input text}', replace=['assembled', 0]),
        'task': node('PrimitiveStringMultiline', value='TASK INSTRUCTIONS: expand {input text}'),
        'assembled': node('PromptAssemblerCompact', prompt_1=' a lake ', prompt_2=' at dawn ',
                          prompt_3='disabled text', enable_3=False, separator='newline'),
    })
    result = extract({'prompt': g})
    assert result['positive'] == 'a lake\n\nat dawn'
    assert 'INSTRUCTIONS' not in json.dumps(result)
    assert 'disabled text' not in result['positive']
    assert len(result['stages']) == 1
    if enabled:
        assert any('output is not stored' in e for e in result['issues'])
    else:
        assert not result['issues']


def test_string_replace_outside_enhancer_keeps_full_text():
    g = graph(['replace', 0])
    g['replace'] = node('StringReplace', string='photo of {input text}', find='{input text}', replace='a lake')
    result = extract({'prompt': g})
    assert result['positive'] == 'photo of a lake'
    assert not result['issues']


def test_instruction_branch_not_a_generation_stage():
    g = {'gen': node('CustomImageGenerator', prompt=['enhance', 0]),
         'enhance': node('TextGenerateV2', prompt='a lake', system_prompt=['instructions', 0]),
         'instructions': node('PromptInstructions', prompt='SYSTEM instructions'),
         'save': node('SaveImage', images=['gen', 0])}
    result = extract({'prompt': g})
    assert result['positive'] == 'a lake'
    assert 'SYSTEM instructions' not in json.dumps(result)
    assert [s['node'] for s in result['stages']] == ['gen']


def test_no_metadata_skipped_and_old_review_rows_migrate(tmp_path):
    library = Library(tmp_path / 'db')
    path = tmp_path / 'plain.png'; png(path)
    library.index(path)
    assert library.listing(review=True)['total'] == 0
    assert library.listing()['counts']['ignored'] == 1
    with library.connect() as db:
        db.execute("UPDATE images SET status='review'")
    assert Library(tmp_path / 'db').listing(review=True)['total'] == 0


def test_extractor_upgrade_preserves_manual_correction(tmp_path):
    library = Library(tmp_path / 'db')
    path = tmp_path / 'a.png'; png(path, graph())
    library.index(path); library.correct(1, 'my corrected prompt')
    with library.connect() as db:
        row = db.execute('SELECT stamp FROM images WHERE id=1').fetchone()
        db.execute('UPDATE images SET stamp=? WHERE id=1', (row['stamp'].rsplit(':',1)[0]+':0',))
    library.refresh_existing()
    for _ in range(100):
        if library.snapshot()['state'] != 'running': break
        time.sleep(.02)
    assert library.get(1)['positive'] == 'my corrected prompt'
    assert library.get(1)['status'] == 'corrected'


def test_accept_groups_matching_review_images(tmp_path):
    library = Library(tmp_path / 'db')
    for name, text in [('ignored', 'candidate'), ('a', 'candidate'), ('b', ' candidate\r\n'),
                       ('c', 'different'), ('target', 'corrected prompt'), ('case', 'Candidate')]:
        g = graph(['unknown', 0]); g['unknown'] = node('UnknownText', text=text)
        path = tmp_path / (name+'.png'); png(path, g); library.index(path)
        if name == 'ignored':
            library.ignore(1)
    path = tmp_path / 'existing.png'; png(path, graph('corrected prompt')); library.index(path)
    result = library.correct(2, ' corrected prompt ')
    assert result['accepted_count'] == 3
    assert library.listing(review=True)['total'] == 2
    assert library.images(result['group_id'], 0)['total'] == 4
    assert library.get(1)['status'] == 'dismissed'
    assert library.get(2)['correction'] == 'corrected prompt'
    assert library.get(2)['extraction']['positive'] == 'candidate'
    assert Library(tmp_path / 'db').images(result['group_id'], 0)['total'] == 4


def test_accept_empty_extraction_does_not_group_unknown_images(tmp_path):
    library = Library(tmp_path / 'db')
    for name in ('a', 'b'):
        path = tmp_path / (name+'.png'); path.write_bytes(b'broken image'); library.index(path)
    assert library.correct(1, 'recovered manually')['accepted_count'] == 1
    assert library.listing(review=True)['total'] == 1


def test_ignore_groups_matching_review_images_only(tmp_path):
    library = Library(tmp_path / 'db')
    for name, text in [('accepted', 'candidate'), ('a', 'candidate'), ('b', ' candidate\r\n'),
                       ('different', 'different'), ('case', 'Candidate')]:
        g = graph(['unknown', 0]); g['unknown'] = node('UnknownText', text=text)
        path = tmp_path / (name+'.png'); png(path, g); library.index(path)
        if name == 'accepted':
            library.correct(1, 'candidate')
    result = library.ignore(2)
    assert result['ignored_count'] == 2
    assert library.listing(review=True)['total'] == 2
    assert library.get(1)['status'] == 'corrected'
    assert library.listing()['total'] == 1
    assert library.ignore(2)['ignored_count'] == 0
    library = Library(tmp_path / 'db')
    for name in ('a', 'b'):
        assert not library.index(tmp_path / (name+'.png'))
    assert library.listing()['counts']['dismissed'] == 2


def test_ignore_empty_prompts_stays_individual(tmp_path):
    library = Library(tmp_path / 'db')
    for name in ('a', 'b'):
        path = tmp_path / (name+'.png'); path.write_bytes(b'broken'); library.index(path)
    assert library.ignore(1)['ignored_count'] == 1
    assert library.listing(review=True)['total'] == 1


def test_ignore_persists_and_changed_image_is_reconsidered(tmp_path):
    library = Library(tmp_path / 'db')
    path = tmp_path / 'review.png'
    g = graph(['unknown', 0]); g['unknown'] = node('UnknownText', text='candidate')
    png(path, g); library.index(path)
    assert library.listing(review=True)['total'] == 1
    library.ignore(1)
    assert library.listing(review=True)['total'] == 0
    assert library.listing()['total'] == 0
    assert path.exists()
    library = Library(tmp_path / 'db')
    assert not library.index(path)
    with library.connect() as db:
        stamp = db.execute('SELECT stamp FROM images WHERE id=1').fetchone()['stamp']
        db.execute('UPDATE images SET stamp=? WHERE id=1', (stamp.rsplit(':', 1)[0]+':0',))
    library.index(path)
    assert library.get(1)['status'] == 'dismissed'
    assert library.listing()['counts']['dismissed'] == 1
    g['unknown']['inputs']['text'] = 'changed candidate with different length'
    png(path, g); library.index(path)
    assert library.listing(review=True)['total'] == 1
    library.correct(1, 'valid corrected prompt')
    with pytest.raises(ValueError, match='Only images needing review'):
        library.ignore(1)
    with pytest.raises(ValueError, match='Image not found'):
        library.ignore(999)


def test_http_auth_origin_and_indexed_images(tmp_path):
    library = Library(tmp_path / "db")
    png(tmp_path / "a.png", graph()); library.index(tmp_path / "a.png")
    server = make_server(library, "test-token")
    worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    url = f"http://127.0.0.1:{server.server_port}"
    def get(path, headers=None):
        return urllib.request.urlopen(urllib.request.Request(url+path, headers=headers or {}), timeout=3)
    try:
        with pytest.raises(urllib.error.HTTPError) as denied:
            get('/api/prompts')
        assert denied.value.code == 403
        with pytest.raises(urllib.error.HTTPError):
            get('/api/prompts', {'X-Library-Token': 'test-token', 'Origin': 'https://example.com'})
        with get('/api/prompts', {'X-Library-Token': 'test-token'}) as response:
            assert json.load(response)['total'] == 1
        with get('/api/thumbnail?id=1&token=test-token') as response:
            assert response.headers['Content-Type'] == 'image/jpeg'
        with get('/') as response:
            assert b'Image prompt library' in response.read()
        g = graph(['unknown', 0]); g['unknown'] = node('UnknownText', text='candidate')
        png(tmp_path / 'review.png', g); library.index(tmp_path / 'review.png')
        for headers, expected in [({}, 403), ({'X-Library-Token': 'test-token'}, 200)]:
            request = urllib.request.Request(url+'/api/ignore', data=b'{"id":2}', headers=headers)
            if expected == 403:
                with pytest.raises(urllib.error.HTTPError) as denied:
                    urllib.request.urlopen(request)
                assert denied.value.code == 403
            else:
                with urllib.request.urlopen(request) as response:
                    assert json.load(response)['status'] == 'dismissed'
        assert library.listing(review=True)['total'] == 0
    finally:
        server.shutdown(); server.server_close(); worker.join()


def test_independent_launch_reuses_process(tmp_path):
    url = ensure_started(tmp_path / 'app')
    try:
        assert ensure_started(tmp_path / 'app') == url
        base, token = url.split('/#')
        request = urllib.request.Request(base+'/api/prompts', headers={'X-Library-Token': token})
        with urllib.request.urlopen(request) as response:
            assert json.load(response)['total'] == 0
    finally:
        base, token = url.split('/#')
        request = urllib.request.Request(base+'/api/quit', data=b'{}', headers={'X-Library-Token': token})
        urllib.request.urlopen(request).close()
        for _ in range(30):
            if not (tmp_path / 'app' / 'session.json').exists():
                break
            time.sleep(.1)


def test_xprompts_launch_route(monkeypatch):
    import image_prompt_library
    root = Path(image_prompt_library.__file__).parent.parent
    package = types.ModuleType('image_library_route_test')
    package.__path__ = [str(root)]
    monkeypatch.setitem(sys.modules, package.__name__, package)
    routes = {}
    class Routes:
        def get(self, path):
            return self.post(path)
        def post(self, path):
            def wrap(function):
                routes[path] = function
                return function
            return wrap
    server = types.ModuleType('server')
    server.PromptServer = types.SimpleNamespace(instance=types.SimpleNamespace(routes=Routes()))
    monkeypatch.setitem(sys.modules, 'server', server)
    monkeypatch.setitem(sys.modules, 'folder_paths', types.ModuleType('folder_paths'))
    aiohttp = types.ModuleType('aiohttp')
    aiohttp.web = types.SimpleNamespace(json_response=lambda data, status=200: (status, data))
    monkeypatch.setitem(sys.modules, 'aiohttp', aiohttp)
    module = importlib.import_module(package.__name__+'.xflows_manager')
    monkeypatch.setattr(module, '_start_image_prompt_library', lambda: 'http://127.0.0.1:1234/#test')
    request = types.SimpleNamespace(headers={'Origin':'http://127.0.0.1:8188'}, scheme='http', host='127.0.0.1:8188')
    status, result = asyncio.run(routes['/xflows/library/image-app/launch'](request))
    assert status == 200 and result['url'].endswith('/#test')
    request.headers['Origin'] = 'http://127.0.0.1'
    assert asyncio.run(module.launch_image_prompt_library(request))[0] == 200
    request.headers['Origin'] = 'http://127.0.0.1:9999'
    assert asyncio.run(module.launch_image_prompt_library(request))[0] == 403
    request.headers['Origin'] = 'null'
    assert asyncio.run(module.launch_image_prompt_library(request))[0] == 403
    request.headers['Origin'] = 'http://127.0.0.1:8188'
    request.headers['Sec-Fetch-Site'] = 'cross-site'
    assert asyncio.run(module.launch_image_prompt_library(request))[0] == 403
    request.headers.pop('Sec-Fetch-Site')
    request.headers['Origin'] = 'https://example.com'
    assert asyncio.run(module.launch_image_prompt_library(request))[0] == 403


def wait_duplicates(library):
    for _ in range(300):
        data = library.duplicates.snapshot()
        if data['state'] != 'running':
            return data
        time.sleep(.01)
    raise AssertionError('Duplicate detection did not finish')


def test_blacklist_persistence_restore_and_new_matches(tmp_path):
    library = Library(tmp_path / 'db')
    png(tmp_path / 'a.png', graph('same prompt')); library.index(tmp_path / 'a.png')
    group = library.listing()['items'][0]['group_id']
    for name in ('review', 'ignored'):
        g = graph(['unknown', 0]); g['unknown'] = node('UnknownText', text='same prompt')
        png(tmp_path / (name+'.png'), g); library.index(tmp_path / (name+'.png'))
    library.ignore(3)
    # Preserve one review and one individually dismissed record beneath the blacklist.
    with library.connect() as db:
        db.execute("UPDATE images SET status='review' WHERE id=2")
    assert library.blacklist_prompt(group)['blacklisted_count'] == 3
    assert library.blacklist_prompt(group)['blacklisted_count'] == 3
    assert library.listing()['total'] == library.listing(review=True)['total'] == 0
    assert library.images(group, 0)['total'] == 0
    assert library.blacklisted()['items'][0]['count'] == 3
    assert library.blacklisted('not present')['total'] == 0
    with pytest.raises(ValueError, match='Restore'):
        library.correct(2, 'same prompt')
    library = Library(tmp_path / 'db')
    assert not library.index(tmp_path / 'a.png')
    png(tmp_path / 'new.png', graph('same prompt')); library.index(tmp_path / 'new.png')
    assert library.listing()['counts']['blacklisted'] == 4
    assert library.restore_prompt(group)['restored_count'] == 4
    assert library.images(group, 0)['total'] == 2
    assert library.listing(review=True)['total'] == 1
    assert library.get(3)['status'] == 'dismissed'
    assert library.restore_prompt(group)['restored_count'] == 0
    library.blacklist_prompt(group)
    png(tmp_path / 'a.png', graph('different prompt now')); library.index(tmp_path / 'a.png')
    assert library.listing()['total'] == 1


def test_duplicate_similarity_settings_and_pair_blacklist(tmp_path):
    from image_prompt_library.duplicates import tokens, similarity
    assert similarity(tokens('A LAKE   at dawn.'), tokens('a lake at dawn.')) == 100
    a, b = tokens('tide diet tide'), tokens('diet tide diet')
    assert similarity(a,b) == similarity(b,a)
    assert similarity(tokens('lake'), tokens('spaceship')) == 0
    library = Library(tmp_path / 'db')
    for i, text in enumerate(('a lake at dawn', 'A lake at dawn', 'a lake at dusk', 'totally different')):
        path = tmp_path / f'{i}.png'; png(path, graph(text)); library.index(path)
    library.duplicates.start(90)
    data = wait_duplicates(library)
    assert data['state'] == 'complete' and data['matches'] == 1
    pair = data['items'][0]
    assert pair['score'] == 100
    assert any(part['changed'] for part in pair['differences'][0])
    assert library.settings()['threshold'] == 90
    library.settings(75)
    assert Library(tmp_path / 'db').settings()['threshold'] == 75
    for invalid in (None, 0, 101, True, '90', float('nan')):
        with pytest.raises(ValueError): library.settings(invalid)
    result = library.blacklist_prompt(pair['right']['group_id'], pair['left']['group_id'], data['id'], data['revision'])
    assert result['blacklisted_count'] == 1
    assert library.duplicates.snapshot()['matches'] == 0
    assert library.images(pair['left']['group_id'], 0)['total'] == 1
    assert library.get(pair['right']['id'])['positive'] == pair['right']['positive']
    library.restore_prompt(pair['right']['group_id'])
    assert library.duplicates.snapshot()['state'] == 'stale'
    with pytest.raises(ValueError, match='changed'):
        library.blacklist_prompt(pair['right']['group_id'], pair['left']['group_id'], data['id'], data['revision'])
    library.duplicates.start(75)
    assert wait_duplicates(library)['matches'] == 3


def test_duplicates_cancel_and_invalidation(tmp_path, monkeypatch):
    import image_prompt_library.duplicates as module
    library = Library(tmp_path / 'db')
    for i in range(5):
        path = tmp_path / f'{i}.png'; png(path, graph('a lake at dawn '+str(i))); library.index(path)
    entered, release = threading.Event(), threading.Event()
    original = module.similarity
    def delayed(a,b):
        entered.set(); release.wait(3); return original(a,b)
    monkeypatch.setattr(module, 'similarity', delayed)
    library.duplicates.start(1); assert entered.wait(2)
    library.duplicates.cancel.set(); release.set()
    assert wait_duplicates(library)['state'] == 'cancelled'
    library.duplicates.start(1)
    assert wait_duplicates(library)['matches'] == 10
    library.correct(1, 'changed after comparison')
    assert library.duplicates.snapshot()['state'] == 'stale'


def test_blacklist_http_validation(tmp_path):
    library = Library(tmp_path / 'db')
    path = tmp_path / 'a.png'; png(path, graph()); library.index(path)
    group = library.listing()['items'][0]['group_id']
    server = make_server(library, 'token'); worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    def call(route, body=None, token='token'):
        request = urllib.request.Request(base+route, data=json.dumps(body).encode() if body is not None else None,
                                         headers={'X-Library-Token':token})
        with urllib.request.urlopen(request) as r: return json.load(r)
    try:
        with pytest.raises(urllib.error.HTTPError) as error: call('/api/blacklist', {'group':group}, '')
        assert error.value.code == 403
        with pytest.raises(urllib.error.HTTPError): call('/api/settings', {'threshold':101})
        assert call('/api/blacklist', {'group':group})['blacklisted_count'] == 1
        assert call('/api/blacklist')['total'] == 1
        assert call('/api/blacklist/restore', {'group':group})['restored_count'] == 1
        assert call('/api/duplicates', {'threshold':90})['state'] in ('running','complete')
        assert call('/api/duplicates')['total'] == 0
    finally:
        server.shutdown(); server.server_close(); worker.join()


def test_blacklist_exact_matching_extractor_refresh_and_corrections(tmp_path):
    library = Library(tmp_path / 'db')
    path = tmp_path / 'accepted.png'; png(path, graph('source prompt')); library.index(path)
    result = library.correct(1, 'Accepted prompt')
    library.blacklist_prompt(result['group_id'])
    with library.connect() as db:
        stamp = db.execute('SELECT stamp FROM images WHERE id=1').fetchone()[0]
        db.execute('UPDATE images SET stamp=? WHERE id=1', (stamp.rsplit(':',1)[0]+':0',))
    library.index(path)
    assert library.listing()['total'] == 0
    assert library.get(1)['correction'] == 'Accepted prompt'
    for i, text in enumerate(('Accepted prompt ', 'accepted prompt', 'Accepted prompts')):
        path = tmp_path / f'new-{i}.png'; png(path, graph(text)); library.index(path)
    assert library.listing()['total'] == 2
    assert library.blacklisted()['items'][0]['count'] == 2
    library.restore_prompt(result['group_id'])
    assert library.get(1)['status'] == 'corrected'
    assert library.images(result['group_id'], 0)['total'] == 2


def test_similarity_long_prompt_boundary_and_pagination(tmp_path):
    from image_prompt_library.duplicates import similarity, tokens
    long = ' '.join(f'word{i}' for i in range(2500))
    assert similarity(tokens(long), tokens(long.upper())) == 100
    assert similarity(tokens('a b c d'), tokens('a b c x')) == 75
    library = Library(tmp_path / 'db')
    for i in range(8):
        path = tmp_path / f'{i}.png'; png(path, graph('shared words '+str(i))); library.index(path)
    library.duplicates.start(66)
    assert wait_duplicates(library)['matches'] == 28
    assert len(library.duplicates.snapshot(1)['items']) == 8
    assert not library.duplicates.snapshot(2)['items']
    library.duplicates.start(100)
    assert wait_duplicates(library)['matches'] == 0
