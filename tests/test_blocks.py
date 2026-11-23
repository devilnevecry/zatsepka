"""Block detection markers per source."""

from __future__ import annotations

import pytest

from app.browser.blocks import detect_block


@pytest.mark.unit
def test_google_sorry_url():
    assert detect_block("google", "https://www.google.com/sorry/index?continue=x", "", "")


@pytest.mark.unit
def test_google_unusual_traffic_text():
    reason = detect_block("google", "https://google.com/maps", "Google", "Our systems have detected unusual traffic from your computer")
    assert reason and "unusual traffic" in reason


@pytest.mark.unit
def test_yandex_captcha():
    assert detect_block("yandex", "https://yandex.ru/showcaptcha?x=1", "", "")
    assert detect_block("yandex", "https://yandex.ru/maps/", "", "Подтвердите, что запросы отправляли вы, а не робот")


@pytest.mark.unit
def test_twogis_block():
    assert detect_block("twogis", "https://2gis.ru/saratov", "Доступ ограничен", "")


@pytest.mark.unit
def test_clean_page_passes():
    assert detect_block("google", "https://www.google.com/maps/search/барбершоп", "барбершоп - Google Maps", "Результаты") is None
    assert detect_block("yandex", "https://yandex.ru/maps/?text=кофейня", "Яндекс Карты", "Найдено 25 организаций") is None
    assert detect_block("twogis", "https://2gis.ru/saratov/search/барбершоп", "2ГИС", "Барбершопы в Саратове") is None


@pytest.mark.unit
def test_unknown_source():
    assert detect_block("bing", "https://bing.com/captcha", "", "") is None
