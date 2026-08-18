import json
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
EXAMPLES = ROOT / "examples"
LEGACY_DOC = ROOT / "docs" / "LEGACY_MIGRATION.md"
DEPRECATED_IDS = {
    "KVGC_GroupConfigurator",
    "KVGC_GroupScopes",
    "KVGC_ConfigSelector",
    "KVGC_ConfigSelectorAdvanced",
}
DEPRECATED_NAMES = {
    "Group Configurator",
    "Group Scopes",
    "Config Selector Advanced",
}
FRONTEND_ONLY_TYPES = {"Note"}


def _package():
    tests_dir = str(ROOT / "tests")
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)
    from test_packaging import _load_package

    return _load_package()


def _active_node_ids():
    return set(_package().NODE_CLASS_MAPPINGS) - DEPRECATED_IDS


def _example_documents():
    paths = sorted(EXAMPLES.glob("*.json"))
    assert len(paths) == 7
    return {path: json.loads(path.read_text(encoding="utf-8")) for path in paths}


def _overlap(left, right):
    lx, ly, lw, lh = map(float, left)
    rx, ry, rw, rh = map(float, right)
    return lx < rx + rw and rx < lx + lw and ly < ry + rh and ry < ly + lh


def _heading_slug(text):
    text = re.sub(r"<[^>]+>", "", text).strip().lower()
    text = re.sub(r"[^a-z0-9 _-]", "", text)
    return re.sub(r"[ _]+", "-", text).strip("-")


def test_readme_is_the_complete_active_node_reference():
    text = README.read_text(encoding="utf-8")
    active = _active_node_ids()
    assert len(active) == 35
    missing = sorted(node_id for node_id in active if f"`{node_id}`" not in text)
    assert missing == [], missing
    for heading in (
        "Image and media loading",
        "Model and LoRA management",
        "Prompting and JsonX",
        "Remote image APIs",
        "Image editing, processing, and swapping",
        "Video output",
        "Workflow configuration and routing",
        "Workflow libraries",
        "Canvas right-click utilities",
    ):
        assert f"## {heading}" in text


def test_examples_are_reproducible_connected_and_cover_all_active_nodes():
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_documentation_examples.py"), "--check"],
        cwd=ROOT,
        check=True,
    )
    documents = _example_documents()
    example_types = {
        node["type"]
        for document in documents.values()
        for node in document.get("nodes", [])
    }
    assert _active_node_ids() <= example_types
    assert example_types.isdisjoint(DEPRECATED_IDS)

    for path, document in documents.items():
        assert document.get("version") == 0.4, path
        assert len(document.get("links", [])) >= 3, path
        assert document.get("groups"), path
        notes = document.get("extra", {}).get("workflowx_example", {})
        for key in ("title", "requirements", "status", "privacy"):
            assert notes.get(key), (path, key)


def test_example_links_and_layout_are_structurally_valid():
    for path, document in _example_documents().items():
        nodes = {node["id"]: node for node in document["nodes"]}
        link_ids = set()
        for link in document["links"]:
            assert len(link) == 6, (path, link)
            link_id, source_id, output_slot, target_id, input_slot, link_type = link
            assert link_id not in link_ids, (path, link_id)
            link_ids.add(link_id)
            assert source_id in nodes and target_id in nodes, (path, link)
            source = nodes[source_id]
            target = nodes[target_id]
            assert 0 <= output_slot < len(source.get("outputs", [])), (path, link)
            assert 0 <= input_slot < len(target.get("inputs", [])), (path, link)
            assert target["inputs"][input_slot].get("link") == link_id, (path, link)
            assert link_id in source["outputs"][output_slot].get("links", []), (path, link)
            source_type = str(source["outputs"][output_slot].get("type"))
            target_type = str(target["inputs"][input_slot].get("type"))
            assert "*" in (source_type, target_type) or source_type == target_type, (
                path,
                link_type,
                source_type,
                target_type,
            )

        node_list = document["nodes"]
        for index, left in enumerate(node_list):
            left_rect = [*left["pos"], *left["size"]]
            for right in node_list[index + 1 :]:
                right_rect = [*right["pos"], *right["size"]]
                assert not _overlap(left_rect, right_rect), (path, left["id"], right["id"])

        groups = document["groups"]
        for index, left in enumerate(groups):
            for right in groups[index + 1 :]:
                assert not _overlap(left["bounding"], right["bounding"]), (
                    path,
                    left["title"],
                    right["title"],
                )


def test_examples_are_sanitized_and_api_credentials_are_blank():
    forbidden_patterns = {
        "absolute Windows path": re.compile(r"[A-Za-z]:[\\/]"),
        "home directory": re.compile(r"(?:/home/|/Users/|\\Users\\)", re.I),
        "embedded data": re.compile(r"(?:data:image/|;base64,)", re.I),
        "URL": re.compile(r"https?://", re.I),
        "UUID/task ID": re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b", re.I),
    }
    for path, document in _example_documents().items():
        raw = path.read_text(encoding="utf-8")
        for label, pattern in forbidden_patterns.items():
            assert not pattern.search(raw), (path, label)
        for node in document["nodes"]:
            if node["type"] in {
                "NanoBanana_Gemini_2_5_Flash_V2",
                "WorkflowX_KieImageAPI",
                "WorkflowX_AtlasImageAPI",
            }:
                assert node.get("widgets_values", [None])[0] == "", (path, node["type"])
        assert "outputs" not in document, path


def test_deprecated_configurators_are_confined_to_migration_guide():
    markdown_files = [README, *sorted((ROOT / "docs").rglob("*.md"))]
    allowed = {LEGACY_DOC.resolve()}
    forbidden_terms = DEPRECATED_IDS | DEPRECATED_NAMES
    leaks = []
    for path in markdown_files:
        if path.resolve() in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        for term in forbidden_terms:
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(term)}(?![A-Za-z0-9_])", text):
                leaks.append(f"{path.relative_to(ROOT)}: {term}")
    assert leaks == [], leaks


def test_all_local_markdown_links_images_and_anchors_resolve():
    markdown_files = [README, *sorted((ROOT / "docs").rglob("*.md")), EXAMPLES / "README.md"]
    link_pattern = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
    broken = []
    for path in markdown_files:
        text = path.read_text(encoding="utf-8")
        for raw_target in link_pattern.findall(text):
            target = raw_target.strip().strip("<>")
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            file_target, _, anchor = target.partition("#")
            resolved = path if not file_target else (path.parent / file_target).resolve()
            if not resolved.exists():
                broken.append(f"{path.relative_to(ROOT)} -> {raw_target}")
                continue
            if anchor and resolved.suffix.lower() == ".md":
                headings = {
                    _heading_slug(match.group(1))
                    for match in re.finditer(r"^#{1,6}\s+(.+?)\s*$", resolved.read_text(encoding="utf-8"), re.M)
                }
                if anchor not in headings:
                    broken.append(f"{path.relative_to(ROOT)} -> missing anchor {raw_target}")
    assert broken == [], broken


def test_referenced_screenshots_are_normalized_and_manifested():
    markdown_files = [README, *sorted((ROOT / "docs").rglob("*.md"))]
    reference_text = "\n".join(path.read_text(encoding="utf-8") for path in markdown_files)
    names = set(re.findall(r"(?:docs/)?images/([^\s)]+\.(?:png|jpg|jpeg|webp))", reference_text, re.I))
    assert names
    invalid = [name for name in names if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*\.(?:png|jpg|jpeg|webp)", name)]
    assert invalid == [], invalid
    manifest = (ROOT / "docs" / "images" / "README.md").read_text(encoding="utf-8")
    missing_manifest = sorted(name for name in names if f"`{name}`" not in manifest)
    assert missing_manifest == [], missing_manifest


def test_live_object_info_contains_example_node_types_when_comfyui_is_running():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8188/object_info", timeout=10) as response:
            object_info = json.load(response)
    except (OSError, urllib.error.URLError):
        return

    package_ids = set(_package().NODE_CLASS_MAPPINGS)
    assert package_ids <= set(object_info)
    assert len(package_ids) == 39
    example_types = {
        node["type"]
        for document in _example_documents().values()
        for node in document["nodes"]
    }
    missing_live = sorted(example_types - set(object_info) - FRONTEND_ONLY_TYPES)
    assert missing_live == [], missing_live


if __name__ == "__main__":
    tests = [
        (name, value)
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    for name, test in tests:
        test()
        print(f"PASS {name}")
