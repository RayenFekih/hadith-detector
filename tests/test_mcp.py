"""Exercise discovery, schemas, evidence and errors through actual MCP sessions."""

import asyncio
import subprocess
import sys
from html.parser import HTMLParser

import pytest

pytest.importorskip("mcp")
from jsonschema import validate
from mcp.shared.memory import create_connected_server_and_client_session

from hadith_detector import HadithDetector
from hadith_detector.mcp.server import INSTRUCTIONS, create_server

from .test_detector import build_fixture

PHRASE = "عن نافع عن ابن عمر"


@pytest.fixture
def detector(tmp_path):
    index, _ = build_fixture(tmp_path, [PHRASE, "عن نافغ عن ابن عمر", PHRASE])
    return HadithDetector.from_directory(index)


def test_protocol_tools_schemas_and_evidence(detector):
    async def exercise():
        async with create_connected_server_and_client_session(create_server(detector)) as client:
            initialized = await client.initialize()
            assert initialized.instructions == INSTRUCTIONS
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            assert set(tools) == {"detect_hadith", "annotate_hadith", "get_hadith"}
            for tool in tools.values():
                assert tool.inputSchema["type"] == tool.outputSchema["type"] == "object"
                assert tool.annotations.readOnlyHint
                assert not tool.annotations.openWorldHint
            config = tools["detect_hadith"].inputSchema["$defs"]["DetectionConfig"]
            assert config["additionalProperties"] is False
            assert config["properties"]["min_match_words"]["minimum"] == 1

            text = "🙂 <&>\r\nعَنْ نَافِع عَن ابْن عُمَر!"
            args = {"text": text, "config": {"max_errors": 1}}
            validate(args, tools["detect_hadith"].inputSchema)
            result = await client.call_tool("detect_hadith", args)
            assert not result.isError
            data = result.structuredContent
            validate(data, tools["detect_hadith"].outputSchema)
            expected = detector.detect(text, max_errors=1)
            assert len(data["matches"]) == len(expected) == 1
            match = data["matches"][0]
            assert text[match["start"] : match["end"]] == match["text"] == expected[0].text
            assert match["match_kind"] == "normalized_exact"
            assert data["interpretation"] == "candidate_textual_matches"
            assert not data["truncated"]
            assert [r["occurrences"][0]["errors"] for r in match["references"]] == [0, 1, 0]
            for ref, original in zip(match["references"], expected[0].references, strict=True):
                assert ref["hadith_key"] == original.record.hadith_key
                assert ref["occurrences"] == [o.to_dict() for o in original.occurrences]
                record = await client.call_tool("get_hadith", {"hadith_key": ref["hadith_key"]})
                validate(record.structuredContent, tools["get_hadith"].outputSchema)
                assert record.structuredContent["record"] == original.record.to_dict()

            annotation = await client.call_tool("annotate_hadith", args)
            validate(annotation.structuredContent, tools["annotate_hadith"].outputSchema)
            assert annotation.structuredContent["original_text"] == text
            html = annotation.structuredContent["html"]
            assert html == detector.annotate(text, max_errors=1)
            assert f'data-start="{match["start"]}"' in html

            class PlainText(HTMLParser):
                def handle_data(self, value):
                    self.parts.append(value)

            parser = PlainText(convert_charrefs=True)
            parser.parts = []
            parser.feed(html)
            assert "".join(parser.parts) == text

            approximate = await client.call_tool(
                "detect_hadith", {"text": "عن نافق عن ابن عمر", "config": {"max_errors": 1}}
            )
            assert approximate.structuredContent["matches"][0]["match_kind"] == "approximate"
            default = await client.call_tool("detect_hadith", {"text": PHRASE})
            assert default.structuredContent["config"]["max_errors"] == 0
            assert default.structuredContent["matches"][0]["total_references"] == 2
            omitted = await client.call_tool(
                "detect_hadith",
                {
                    "text": "عن نافع ابن عمر",
                    "config": {"min_match_words": 4, "max_missing_words": 1},
                },
            )
            omission = omitted.structuredContent["matches"][0]
            assert omission["match_kind"] == "approximate"
            assert omission["missing_words"] == 1
            assert omission["references"][0]["occurrences"][0]["omitted_source_tokens"]
            empty = await client.call_tool("detect_hadith", {"text": ""})
            assert empty.structuredContent["matches"] == []
            empty_html = await client.call_tool("annotate_hadith", {"text": ""})
            assert empty_html.structuredContent["html"] == ""

    asyncio.run(exercise())


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("get_hadith", {"hadith_key": "bukhari:999999999"}),
        ("get_hadith", {"hadith_key": ""}),
        ("get_hadith", {"hadith_key": "invalid"}),
        ("get_hadith", {"hadith_key": 1}),
        ("detect_hadith", {}),
        ("detect_hadith", {"text": 123}),
        ("detect_hadith", {"text": PHRASE, "config": {"min_match_words": 0}}),
        ("detect_hadith", {"text": PHRASE, "config": {"max_errors": True}}),
        ("detect_hadith", {"text": PHRASE, "config": {"max_errors": "1"}}),
        ("detect_hadith", {"text": PHRASE, "config": {"max_missing_words": -1}}),
        ("detect_hadith", {"text": PHRASE, "config": {"min_match_words": 1.5}}),
        ("detect_hadith", {"text": PHRASE, "config": {"unknown": 1}}),
        ("detect_hadith", {"text": PHRASE, "config": []}),
        ("detect_hadith", {"text": PHRASE, "match_offset": -1}),
        ("detect_hadith", {"text": PHRASE, "reference_limit": 0}),
        ("detect_hadith", {"text": PHRASE, "occurrence_limit": 101}),
        ("annotate_hadith", {"text": "\x00"}),
        ("annotate_hadith", {"text": "\ud800"}),
        ("missing_tool", {}),
    ],
)
def test_protocol_errors_and_recovery(detector, tool, args):
    async def exercise():
        async with create_connected_server_and_client_session(create_server(detector)) as client:
            assert (await client.call_tool(tool, args)).isError
            assert not (await client.call_tool("get_hadith", {"hadith_key": "fixture:1"})).isError

    asyncio.run(exercise())


def test_pagination_preserves_all_evidence(detector):
    async def exercise():
        async with create_connected_server_and_client_session(create_server(detector)) as client:
            keys = []
            for offset in range(3):
                result = await client.call_tool(
                    "detect_hadith",
                    {
                        "text": PHRASE,
                        "config": {"max_errors": 1},
                        "reference_offset": offset,
                        "reference_limit": 1,
                    },
                )
                data = result.structuredContent
                assert data["truncated"]
                match = data["matches"][0]
                assert match["total_references"] == 3
                assert match["next_reference_offset"] == (offset + 1 if offset < 2 else None)
                keys.append(match["references"][0]["hadith_key"])
            assert keys == ["fixture:1", "fixture:2", "fixture:3"]
            result = await client.call_tool("detect_hadith", {"text": PHRASE, "match_offset": 99})
            assert result.structuredContent["matches"] == []
            assert result.structuredContent["truncated"]

    asyncio.run(exercise())


def test_match_and_occurrence_pagination(tmp_path):
    index, _ = build_fixture(tmp_path, [PHRASE + " ! " + PHRASE])
    detector = HadithDetector.from_directory(index)
    text = PHRASE + " شيءمختلف " + PHRASE

    async def exercise():
        async with create_connected_server_and_client_session(create_server(detector)) as client:
            for match_offset in range(2):
                for occurrence_offset in range(2):
                    response = await client.call_tool(
                        "detect_hadith",
                        {
                            "text": text,
                            "match_offset": match_offset,
                            "match_limit": 1,
                            "occurrence_offset": occurrence_offset,
                            "occurrence_limit": 1,
                        },
                    )
                    data = response.structuredContent
                    assert data["total_matches"] == 2
                    assert data["truncated"]
                    assert data["next_match_offset"] == (1 if match_offset == 0 else None)
                    ref = data["matches"][0]["references"][0]
                    assert ref["total_occurrences"] == 2
                    assert ref["next_occurrence_offset"] == (1 if occurrence_offset == 0 else None)
                    original = detector.detect(text)[match_offset]
                    assert ref["occurrences"] == [
                        original.references[0].occurrences[occurrence_offset].to_dict()
                    ]

    asyncio.run(exercise())


def test_shared_detector_is_loaded_once(detector, monkeypatch):
    calls = []

    def load():
        calls.append(True)
        return detector

    monkeypatch.setattr("hadith_detector.mcp.server.HadithDetector", load)
    server = create_server()
    assert calls == []

    async def exercise():
        async with create_connected_server_and_client_session(server) as client:
            await client.list_tools()
            assert calls == []
            await client.call_tool("detect_hadith", {"text": PHRASE})
            await client.call_tool("annotate_hadith", {"text": PHRASE})
            await client.call_tool("get_hadith", {"hadith_key": "fixture:1"})

    asyncio.run(exercise())
    assert len(calls) == 1


def test_optional_import_and_missing_extra(tmp_path):
    script = """
import importlib.abc
import sys
class NoMCP(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'mcp' or fullname.startswith('mcp.'):
            raise ModuleNotFoundError('blocked optional SDK', name='mcp')
sys.meta_path.insert(0, NoMCP())
import hadith_detector
import hadith_detector.mcp
assert 'mcp' not in sys.modules
assert 'pydantic' not in sys.modules
hadith_detector.mcp.main()
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", script], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode != 0
    assert result.stdout == ""
    assert 'pip install "hadith-detector[mcp]"' in result.stderr
    assert "Traceback" not in result.stderr
