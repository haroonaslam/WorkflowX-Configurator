import io
import json
import pathlib
import sys
import tempfile
import types
import unittest
from unittest import mock

import torch
from PIL import Image


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from remote_image_api import catalogs
from remote_image_api import nodes
from remote_image_api import runtime


def png_bytes(color=(20, 40, 60)):
    buffer = io.BytesIO()
    Image.new("RGB", (3, 2), color).save(buffer, "PNG")
    return buffer.getvalue()


class FakeKieClient:
    create_calls = 0
    status_calls = 0
    upload_calls = 0
    last_payload = None

    def __init__(self, api_key):
        self.api_key = api_key
        self.provider = "kie"

    def upload(self, _data, _index):
        type(self).upload_calls += 1
        return "https://files.example/ref.png"

    def create(self, payload):
        type(self).create_calls += 1
        type(self).last_payload = payload
        return "task-one"

    def status(self, _task_id):
        type(self).status_calls += 1
        return {"state": "completed", "url": "https://files.example/out.png", "error": ""}

    def download(self, _url):
        return png_bytes()


class RemoteImageCatalogTests(unittest.TestCase):
    def test_catalogs_match_selected_gemmobi_generative_scope(self):
        self.assertEqual(len(catalogs.KIE_PROFILES), 12)
        self.assertEqual(len(catalogs.ATLAS_PROFILES), 12)
        self.assertNotIn("topaz-upscale", catalogs.PROFILE_MAPS["kie"])
        self.assertEqual(catalogs.PROFILE_MAPS["kie"]["gpt2"]["max_references"], 14)
        self.assertEqual(catalogs.PROFILE_MAPS["atlas"]["kontext"]["max_references"], 1)
        self.assertEqual(catalogs.PROFILE_MAPS["atlas"]["nano-banana-pro"]["max_references"], 10)

    def test_packaged_contract_corrects_known_catalog_drift(self):
        self.assertEqual(catalogs.CONTRACTS["schema_version"], "2.0.0")
        expected_aspects = ["1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]
        for model in ("nano-banana-2", "nano-banana-pro"):
            profile = catalogs.PROFILE_MAPS["kie"][model]
            self.assertEqual(profile["aspect_ratios"], expected_aspects)
            self.assertEqual(profile["output_formats"], ["default", "png", "jpeg"])
        seedream = catalogs.PROFILE_MAPS["kie"]["seedream-5-pro"]
        self.assertEqual(seedream["sizes"], [])
        self.assertEqual(seedream["quality_options"], ["basic", "high"])
        self.assertFalse(seedream["sends_n"])

    def test_public_catalog_exposes_canonical_ui_descriptors(self):
        atlas_gpt2 = next(item for item in catalogs.public_catalogs()["atlas"] if item["id"] == "gpt2")
        by_widget = {item["widget"]: item for item in atlas_gpt2["controls"]}
        self.assertEqual(by_widget["image_size"]["options"][0], "1024x1024")
        self.assertEqual(by_widget["output_format"]["options"], ["jpeg", "png"])
        self.assertEqual(atlas_gpt2["custom_size"]["max_edge"], 3840)

    def test_kie_routes_t2i_and_i2i_and_uses_provider_image_field(self):
        profile = catalogs.PROFILE_MAPS["kie"]["grok-imagine"]
        t2i = runtime.build_kie_payload(profile, "cat", "1:1", "", [], {"enable_pro": True, "nsfw_checker": False})
        i2i = runtime.build_kie_payload(profile, "cat", "1:1", "", ["https://ref"], {"enable_pro": True, "nsfw_checker": False})
        self.assertEqual(t2i["model"], "grok-imagine/text-to-image")
        self.assertTrue(t2i["input"]["enable_pro"])
        self.assertEqual(i2i["model"], "grok-imagine/image-to-image")
        self.assertEqual(i2i["input"]["image_urls"], ["https://ref"])
        self.assertNotIn("enable_pro", i2i["input"])
        self.assertNotIn("aspect_ratio", i2i["input"])

    def test_kie_model_family_payloads(self):
        wan = runtime.build_kie_payload(catalogs.PROFILE_MAPS["kie"]["wan-2-7"], "p", "16:9", "2K", [], {"thinking_mode": True, "watermark": True, "seed_enabled": True, "seed": 4, "enable_sequential": True})
        self.assertEqual(wan["model"], "wan/2-7-image")
        self.assertEqual(wan["input"]["resolution"], "2K")
        self.assertEqual(wan["input"]["seed"], 4)
        gpt2 = runtime.build_kie_payload(catalogs.PROFILE_MAPS["kie"]["gpt2"], "p", "16:9", "4K", [], {"nsfw_checker": False})
        self.assertEqual(gpt2["input"]["resolution"], "4K")
        self.assertFalse(gpt2["input"]["nsfw_checker"])
        qwen = runtime.build_kie_payload(catalogs.PROFILE_MAPS["kie"]["qwen2"], "p", "3:4", "", ["https://ref"], {"seed_enabled": True, "seed": 9, "output_format": "jpeg"})
        self.assertEqual(qwen["input"]["image_url"], "https://ref")
        self.assertEqual(qwen["input"]["image_size"], "3:4")

    def test_atlas_model_family_payloads(self):
        gpt = runtime.build_atlas_payload(catalogs.PROFILE_MAPS["atlas"]["gpt2"], "p", "1:1", "1024x1024", ["https://ref"], {"quality": "high", "output_format": "png", "input_fidelity": "low"})
        self.assertEqual(gpt["model"], "openai/gpt-image-2/edit")
        self.assertEqual(gpt["images"], ["https://ref"])
        self.assertEqual(gpt["input_fidelity"], "low")
        banana = runtime.build_atlas_payload(catalogs.PROFILE_MAPS["atlas"]["nano-banana-2"], "p", "16:9", "2K", [], {"enable_web_search": True, "enable_image_search": True, "media_resolution": "high", "output_format": "png"})
        self.assertEqual(banana["resolution"], "2k")
        self.assertTrue(banana["enable_image_search"])
        kontext = runtime.build_atlas_payload(catalogs.PROFILE_MAPS["atlas"]["kontext"], "p", "9:16", "720*1280", ["https://ref"], {"guidance_scale": 4.5, "num_inference_steps": 30, "enable_safety_checker": False})
        self.assertEqual(kontext["image"], "https://ref")
        self.assertEqual(kontext["size"], "720*1280")
        self.assertFalse(kontext["enable_safety_checker"])

    def test_contract_driven_custom_size_and_seedream_payloads(self):
        qwen = catalogs.PROFILE_MAPS["atlas"]["qwen2"]
        payload = runtime.build_atlas_payload(qwen, "p", "1:1", "1024*1024", [], {
            "custom_size_enabled": True, "custom_width": 1536, "custom_height": 1024,
            "seed_enabled": False,
        })
        self.assertEqual(payload["size"], "1536*1024")
        self.assertEqual(payload["seed"], -1)
        seedream = runtime.build_kie_payload(catalogs.PROFILE_MAPS["kie"]["seedream-5-pro"], "p", "4:3", "basic", [], {"quality": "high", "output_format": "jpeg", "nsfw_checker": True})
        self.assertEqual(seedream["input"]["quality"], "high")
        self.assertNotIn("resolution", seedream["input"])
        self.assertNotIn("n", seedream["input"])

    def test_kie_gpt2_custom_and_auto_resolution_contract(self):
        profile = catalogs.PROFILE_MAPS["kie"]["gpt2"]
        custom = {"custom_size_enabled": True, "custom_size_auto": False, "custom_width": 1280, "custom_height": 768, "nsfw_checker": False}
        runtime.validate_generation(profile, "16:9", "1K", 0, "prompt", custom)
        payload = runtime.build_kie_payload(profile, "prompt", "16:9", "1K", [], custom)
        self.assertEqual(payload["input"]["resolution"], "1280x768")
        automatic = {**custom, "custom_size_auto": True}
        runtime.validate_generation(profile, "auto", "1K", 0, "prompt", automatic)
        self.assertEqual(runtime.build_kie_payload(profile, "prompt", "auto", "1K", [], automatic)["input"]["resolution"], "auto")
        with self.assertRaisesRegex(ValueError, "at least"):
            runtime.validate_generation(profile, "1:1", "1K", 0, "prompt", {**custom, "custom_width": 64, "custom_height": 64})

    def test_validation_rejects_reference_overflow_before_upload(self):
        profile = catalogs.PROFILE_MAPS["atlas"]["kontext"]
        with self.assertRaisesRegex(ValueError, "up to 1"):
            runtime.validate_generation(profile, "1:1", "1024*1024", 2)

    def test_every_profile_builds_both_supported_routes(self):
        settings = {
            "quality": "medium", "nsfw_checker": True, "thinking_mode": True,
            "seed_enabled": True, "seed": 3, "watermark": False,
            "enable_sequential": False, "output_format": "png", "input_fidelity": "high",
            "enable_web_search": False, "enable_image_search": False,
            "media_resolution": "default", "guidance_scale": 3.5,
            "num_inference_steps": 28, "enable_safety_checker": True,
        }
        for provider, profiles in catalogs.PROFILES.items():
            for profile in profiles:
                with self.subTest(provider=provider, model=profile["id"]):
                    aspect = (profile.get("aspect_ratios") or ["1:1"])[0]
                    size_options = runtime.selected_size_options(profile)
                    size = size_options[0] if size_options else ""
                    runtime.validate_generation(profile, aspect, size, 0)
                    builder = runtime.build_kie_payload if provider == "kie" else runtime.build_atlas_payload
                    t2i = builder(profile, "prompt", aspect, size, [], settings)
                    i2i = builder(profile, "prompt", aspect, size, ["https://ref"], settings)
                    self.assertTrue(t2i["model"])
                    self.assertTrue(i2i["model"])
                    image_field = profile["input_image_field"]
                    self.assertIn(image_field, i2i["input"] if provider == "kie" else i2i)

    def test_tensor_round_trip_has_comfyui_shape(self):
        source = torch.zeros((2, 3, 4, 3), dtype=torch.float32)
        frames = runtime.tensor_images([source])
        self.assertEqual(len(frames), 2)
        restored = runtime.image_bytes_to_tensor(runtime.tensor_to_png(frames[0]))
        self.assertEqual(tuple(restored.shape), (1, 3, 4, 3))

    def test_reference_resize_and_placeholder_canvas(self):
        source = torch.zeros((1, 500, 1000, 3), dtype=torch.float32)
        resized = Image.open(io.BytesIO(runtime.tensor_to_png(source[0], 512)))
        self.assertEqual(resized.size, (512, 256))
        profile = catalogs.PROFILE_MAPS["atlas"]["gpt2"]
        placeholder = runtime.placeholder_tensor(profile, "16:9", "2048x1152", {})
        self.assertEqual(tuple(placeholder.shape), (1, 1152, 2048, 3))


class RemoteImagePendingTests(unittest.TestCase):
    def setUp(self):
        FakeKieClient.create_calls = 0
        FakeKieClient.status_calls = 0
        FakeKieClient.upload_calls = 0
        FakeKieClient.last_payload = None
        self.temp = tempfile.TemporaryDirectory()
        self.store = runtime.PendingStore(pathlib.Path(self.temp.name) / "pending.json")

    def tearDown(self):
        self.temp.cleanup()

    def arguments(self, mode="generate"):
        return dict(
            api_key="super-secret", model="wan-2-7", prompt="portrait", aspect_ratio="1:1",
            image_size="1K", timeout_seconds=30, poll_interval_seconds=2, quality="medium",
            nsfw_checker=True, thinking_mode=False, watermark=False, seed_enabled=False, seed=0,
            enable_sequential=False, output_format="png", enable_pro=False, input_fidelity="high",
            enable_web_search=False, enable_image_search=False, media_resolution="default",
            guidance_scale=3.5, num_inference_steps=28, enable_safety_checker=True,
            custom_size_enabled=False, custom_size_auto=False, custom_width=1024, custom_height=1024,
            reference_max_edge=5120, show_payload=False,
            retrieval_mode=mode, unique_id="42",
        )

    def test_timeout_then_force_retrieve_never_resubmits(self):
        node = nodes.KieImageAPINode()
        node.client_class = FakeKieClient
        with mock.patch.object(nodes, "PendingStore", return_value=self.store), mock.patch.object(nodes, "wait_for_result", side_effect=TimeoutError("timed out")):
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                node.generate_image(**self.arguments())
        pending = self.store.get("kie", "42")
        self.assertEqual(pending["task_id"], "task-one")
        self.assertEqual(FakeKieClient.create_calls, 1)

        with mock.patch.object(nodes, "PendingStore", return_value=self.store), mock.patch.object(nodes, "wait_for_result", return_value="https://files.example/out.png"):
            result = node.generate_image(**self.arguments("force_retrieve"))
        self.assertEqual(FakeKieClient.create_calls, 1)
        self.assertIsNone(self.store.get("kie", "42"))
        self.assertEqual(tuple(result["result"][0].shape), (1, 2, 3, 3))

    def test_existing_pending_blocks_replacement_generation(self):
        self.store.put("kie", "42", {"task_id": "already-paid", "provider": "kie"})
        node = nodes.KieImageAPINode()
        node.client_class = FakeKieClient
        with mock.patch.object(nodes, "PendingStore", return_value=self.store):
            with self.assertRaisesRegex(RuntimeError, "replacement paid task was not submitted"):
                node.generate_image(**self.arguments())
        self.assertEqual(FakeKieClient.create_calls, 0)

    def test_registry_and_fingerprint_do_not_persist_secrets(self):
        fingerprint = runtime.request_fingerprint("kie", "wan-2-7", "prompt", "t2i", 0, {"api_key": "secret", "seed": 1})
        self.store.put("kie", "1", {"task_id": "task", "request_fingerprint": fingerprint})
        raw = pathlib.Path(self.store.path).read_text(encoding="utf-8")
        self.assertNotIn("secret", raw)
        self.assertNotIn("prompt", raw)

    def test_forget_pending_removes_only_local_record(self):
        self.store.put("atlas", "8", {"task_id": "remote-still-running"})
        self.assertTrue(self.store.delete("atlas", "8"))
        self.assertIsNone(self.store.get("atlas", "8"))

    def test_stop_continue_forgets_pending_and_returns_placeholder(self):
        node = nodes.KieImageAPINode()
        node.client_class = FakeKieClient
        with mock.patch.object(nodes, "PendingStore", return_value=self.store), mock.patch.object(nodes, "wait_for_result", side_effect=runtime.LocalCancellation("continue")):
            result = node.generate_image(**self.arguments())
        self.assertIsNone(self.store.get("kie", "42"))
        self.assertEqual(tuple(result["result"][0].shape), (1, 1024, 1024, 3))
        self.assertEqual(FakeKieClient.create_calls, 1)

    def test_stop_retrieve_preserves_submitted_task(self):
        node = nodes.KieImageAPINode()
        node.client_class = FakeKieClient
        with mock.patch.object(nodes, "PendingStore", return_value=self.store), mock.patch.object(nodes, "wait_for_result", side_effect=runtime.LocalCancellation("retrieve")):
            with self.assertRaisesRegex(RuntimeError, "Force Retrieve"):
                node.generate_image(**self.arguments())
        self.assertEqual(self.store.get("kie", "42")["task_id"], "task-one")
        self.assertEqual(FakeKieClient.create_calls, 1)

    def test_cancellation_registry_only_accepts_active_nodes(self):
        self.assertFalse(runtime.CancellationRegistry.request("kie", "inactive", "retrieve"))
        runtime.CancellationRegistry.begin("kie", "active")
        self.assertTrue(runtime.CancellationRegistry.request("kie", "active", "continue"))
        with self.assertRaises(runtime.LocalCancellation) as raised:
            runtime.CancellationRegistry.check("kie", "active")
        self.assertEqual(raised.exception.mode, "continue")
        runtime.CancellationRegistry.finish("kie", "active")


class ProviderParserTests(unittest.TestCase):
    def test_kie_create_and_result_json_status_shapes(self):
        client = runtime.KieClient("secret")
        with mock.patch.object(client, "_json_request", return_value=(200, {"code": 200, "data": {"taskId": "abc"}}, "{}")):
            self.assertEqual(client.create({"model": "m", "input": {}}), "abc")
        response = {"code": 200, "data": {"state": "success", "resultJson": json.dumps({"resultUrls": ["https://out"]})}}
        with mock.patch.object(client, "_json_request", return_value=(200, response, "{}")):
            self.assertEqual(client.status("abc")["url"], "https://out")

    def test_kie_upload_403_1010_uses_stream_fallback(self):
        client = runtime.KieClient("secret")
        with mock.patch.object(client, "_json_request", return_value=(403, {"code": 403, "msg": "Cloudflare 1010"}, "1010")), mock.patch.object(client, "_multipart_request", return_value=(200, {"code": 200, "success": True, "data": {"downloadUrl": "https://uploaded"}}, "{}")) as stream:
            self.assertEqual(client.upload(png_bytes(), 1), "https://uploaded")
        stream.assert_called_once()

    def test_atlas_task_id_and_nested_output_shapes(self):
        client = runtime.AtlasClient("secret")
        with mock.patch.object(client, "_json_request", return_value=(200, {"code": 200, "data": {"predictionId": "prediction-1"}}, "{}")):
            self.assertEqual(client.create({"model": "m"}), "prediction-1")
        response = {"data": {"status": "completed", "result": {"images": [{"downloadUrl": "https://atlas-out"}]}}}
        with mock.patch.object(client, "_json_request", return_value=(200, response, "{}")):
            self.assertEqual(client.status("prediction-1")["url"], "https://atlas-out")

    def test_download_retry_reuses_same_url(self):
        client = runtime.KieClient("secret")
        good = mock.MagicMock()
        good.__enter__.return_value.read.return_value = png_bytes()
        with mock.patch("urllib.request.urlopen", side_effect=[OSError("temporary"), good]) as opened, mock.patch("time.sleep"):
            self.assertTrue(client.download("https://same-result"))
        self.assertEqual(opened.call_count, 2)
        self.assertEqual(opened.call_args_list[0].args[0].full_url, "https://same-result")
        self.assertEqual(opened.call_args_list[1].args[0].full_url, "https://same-result")

    def test_polling_retries_transient_status_without_resubmission(self):
        client = FakeKieClient("key")
        with mock.patch.object(client, "status", side_effect=[OSError("temporary"), {"state": "completed", "url": "https://out", "error": ""}]) as status, mock.patch.object(runtime.time, "sleep"):
            self.assertEqual(runtime.wait_for_result(client, "same-task", 30, 2), "https://out")
        self.assertEqual(status.call_count, 2)

    def test_status_events_use_node_scoped_websocket_contract(self):
        sender = mock.Mock()
        fake_server = types.SimpleNamespace(PromptServer=types.SimpleNamespace(instance=types.SimpleNamespace(send_sync=sender)))
        with mock.patch.dict(sys.modules, {"server": fake_server}):
            runtime.emit_status("kie", "42", "polling", "still running", poll_attempt=3)
        event, payload = sender.call_args.args
        self.assertEqual(event, "workflowx.remote_image.status")
        self.assertEqual(payload["node_id"], "42")
        self.assertEqual(payload["poll_attempt"], 3)

    def test_redaction_removes_secrets_and_signed_queries(self):
        message = runtime.redact("Authorization: secret https://example/out.png?token=private", "secret")
        self.assertNotIn("private", message)
        self.assertNotIn("secret", message)
        self.assertIn("[REDACTED_QUERY]", message)


class RemoteImageContractTests(unittest.TestCase):
    def test_node_contract_and_dynamic_frontend(self):
        for cls in (nodes.KieImageAPINode, nodes.AtlasImageAPINode):
            inputs = cls.INPUT_TYPES()
            self.assertEqual(cls.RETURN_TYPES, ("IMAGE",))
            self.assertEqual(cls.CATEGORY, "WorkflowX_Configurator/Image/API")
            self.assertIn("image_1", inputs["optional"])
            self.assertIn("image_14", inputs["optional"])
            self.assertEqual(inputs["hidden"]["unique_id"], "UNIQUE_ID")
        self.assertFalse(nodes.KieImageAPINode.INPUT_TYPES()["required"]["thinking_mode"][1]["default"])
        self.assertTrue(nodes.AtlasImageAPINode.INPUT_TYPES()["required"]["thinking_mode"][1]["default"])
        javascript = (ROOT / "web" / "js" / "remote_image_api.js").read_text(encoding="utf-8")
        for token in ("MAX_IMAGES = 14", "onConnectionsChange", "addDOMWidget", "workflowx.remote_image.status", "Queue Generation", "Stop & Continue", "Stop & Retrieve Later", "Force Retrieve", "Forget Pending", "app.queuePrompt", "retrieval_mode", "MAX_LOG_LINES"):
            self.assertIn(token, javascript)


if __name__ == "__main__":
    unittest.main()
