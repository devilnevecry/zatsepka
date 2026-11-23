"""Peek tool: JSON tree, path extraction, grep, HTML outline."""

from __future__ import annotations

import json

import pytest

from app.tools import peek

SAMPLE = {
    "data": {
        "items": [
            {"name": "Барбершоп Борода", "phones": ["+78452111111"], "rating": 4.8},
            {"name": "Кофейня Зерно", "phones": [], "rating": None},
        ],
        "total": 2,
    },
    "status": "ok",
}


@pytest.mark.unit
def test_json_tree_types_and_lengths():
    lines = peek.json_tree(SAMPLE, depth=4)
    text = "\n".join(lines)
    assert "items: list[2]" in text
    assert "name: Барбершоп Борода" in text
    assert "rating: float" in text
    assert "total: int" in text


@pytest.mark.unit
def test_json_tree_depth_limit():
    lines = peek.json_tree(SAMPLE, depth=1)
    text = "\n".join(lines)
    assert "items: list[2]" in text
    assert "Барбершоп" not in text


@pytest.mark.unit
def test_string_cut():
    data = {"s": "x" * 200}
    lines = peek.json_tree(data)
    assert len(lines[0]) < 100
    assert "…" in lines[0]


@pytest.mark.unit
def test_get_path():
    assert peek.get_path(SAMPLE, "data.items.0.name") == "Барбершоп Борода"
    assert peek.get_path(SAMPLE, "data.total") == 2
    with pytest.raises((KeyError, IndexError)):
        peek.get_path(SAMPLE, "data.items.9.name")


@pytest.mark.unit
def test_grep_json_paths():
    hits = peek.grep_json(SAMPLE, "борода")
    assert hits and hits[0][0] == "data.items.0.name"
    hits2 = peek.grep_json(SAMPLE, "несуществующий")
    assert hits2 == []


@pytest.mark.unit
def test_grep_limit():
    data = {"a": ["match"] * 50}
    hits = peek.grep_json(data, "match", limit=10)
    assert len(hits) == 10


@pytest.mark.unit
def test_html_outline_only_stable_attrs():
    html = """<html><body><div class="x9f3a" role="feed" aria-label="Результаты">
    <a class="hashed" data-item-id="123" href="/maps/place/x">Карточка</a></div></body></html>"""
    lines = peek.html_outline(html)
    text = "\n".join(lines)
    assert 'role="feed"' in text
    assert 'aria-label="Результаты"' in text
    assert 'data-item-id="123"' in text
    assert "x9f3a" not in text
    assert "hashed" not in text


@pytest.mark.unit
def test_load_any_google_prefix(tmp_path):
    p = tmp_path / "resp.json"
    p.write_text(")]}'\n" + json.dumps({"d": "[1,2]"}), encoding="utf-8")
    kind, data = peek.load_any(p)
    assert kind == "json"
    assert data["d"] == "[1,2]"


@pytest.mark.unit
def test_main_on_sample(tmp_path, capsys):
    p = tmp_path / "s.json"
    p.write_text(json.dumps(SAMPLE, ensure_ascii=False), encoding="utf-8")
    assert peek.main([str(p), "--path", "data.items.0.name"]) == 0
    out = capsys.readouterr().out
    assert "Барбершоп Борода" in out
