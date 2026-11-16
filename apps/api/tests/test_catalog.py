"""Catalog derivation: derive from the real text, never invent."""

import pandas as pd
import pytest

from cartiq_api.catalog import (
    FALLBACK_CATEGORY,
    UNAVAILABLE_FIELDS,
    build_catalog,
    categorise,
    coverage_report,
    extract_attributes,
)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("15CM CHRISTMAS GLASS BALL 20 LIGHTS", "seasonal.christmas"),
        ("BLUE FELT EASTER EGG BASKET", "seasonal.easter"),
        ("SILVER HEART NECKLACE", "jewellery"),
        ("SET/6 PURPLE BUTTERFLY T-LIGHTS", "home.lighting"),
        ("BLUE SAVANNAH PICNIC HAMPER FOR 2", "home.storage"),
        ("RED 3 PIECE MINI DOTS CUTLERY SET", "kitchen.dining"),
        ("FAMILY ALBUM WHITE PICTURE FRAME", "home.decor"),
        ("JUMBO SHOPPER VINTAGE RED PAISLEY", "bags.luggage"),
        ("SOMETHING ENTIRELY UNFAMILIAR", FALLBACK_CATEGORY),
    ],
)
def test_categorisation(title, expected):
    assert categorise(title) == expected


def test_seasonal_rules_win_over_product_type():
    # A christmas mug is a christmas line first: seasonal cuts across types and
    # is what a merchandiser actually plans around.
    assert categorise("CHRISTMAS MUG") == "seasonal.christmas"


def test_attribute_extraction():
    attributes = extract_attributes("SET OF 6 RED RETROSPOT GLASS TEA LIGHT HOLDERS")
    assert attributes["colour"] == ["Red"]
    assert attributes["material"] == ["Glass"]
    assert attributes["pattern"] == ["Retrospot"]
    assert attributes["pack_size"] == 6


def test_absent_attributes_stay_absent():
    # An empty string would look like real data; a missing key does not.
    assert extract_attributes("PLAIN ITEM") == {}


def test_grey_and_gray_are_one_colour():
    assert extract_attributes("GRAY STONE POT")["colour"] == ["Grey"]
    assert extract_attributes("GREY STONE POT")["colour"] == ["Grey"]


def test_colour_matching_is_word_bounded():
    # "REDUCED" must not register as the colour red.
    assert "colour" not in extract_attributes("REDUCED PRICE ITEM")


def test_build_catalog_flags_every_derived_field():
    products = pd.DataFrame(
        [{"product_id": "85048", "title": "RED GLASS CHRISTMAS BALL", "price": 6.95}]
    )
    catalog = build_catalog(products)
    row = catalog.iloc[0]

    assert row["category_path"] == "seasonal.christmas"
    # pandas stores this as numpy.bool_, so compare by value.
    assert bool(row["generated"]) is True
    assert "category" in row["generated_fields"]
    assert "attributes.colour" in row["generated_fields"]
    # Title and price came from the source, so they are not flagged.
    assert "title" not in row["generated_fields"]
    assert "price" not in row["generated_fields"]


def test_fields_the_source_lacks_are_null_not_guessed():
    products = pd.DataFrame([{"product_id": "1", "title": "RED MUG", "price": 2.5}])
    row = build_catalog(products).iloc[0]
    for field in UNAVAILABLE_FIELDS:
        assert row[field] is None, f"{field} should be NULL, not invented"


def test_coverage_report_exposes_the_real_gaps():
    products = pd.DataFrame(
        [
            {"product_id": "1", "title": "RED GLASS BAUBLE", "price": 1.0},
            {"product_id": "2", "title": "UNFAMILIAR THING", "price": 2.0},
        ]
    )
    report = coverage_report(build_catalog(products))
    assert report["title"] == 1.0
    assert report["brand"] == 0.0
    assert report["gtin"] == 0.0
    assert report["category_derived"] == 0.5


def test_empty_catalog_is_typed_not_crashing():
    assert build_catalog(pd.DataFrame()).empty
    assert coverage_report(pd.DataFrame()) == {}
