"""Catalog construction and attribute derivation.

The source dataset gives a product code, a free-text description and a price.
It has no category, no brand, no GTIN, no image and no structured attributes.

Two rules govern what happens next:

1. **Derive, never invent.** Category and attributes are extracted from the real
   description text by deterministic rules. Brand, GTIN and image stay NULL
   because nothing in the source supports a value, and guessing one would be a
   fabrication a merchandiser could act on.
2. **Label everything derived.** Each product records `generated_fields`, and
   the UI marks those values as derived. This is also what makes the Module 6
   readiness score meaningful: most of these products genuinely are missing
   brand, GTIN and imagery, and that is a real finding about the catalog.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

#: Ordered (category_path, keywords). First match wins, so the more specific
#: rules — seasonal lines, which cut across every product type — come first.
CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "seasonal.christmas",
        ("CHRISTMAS", "XMAS", "ADVENT", "SANTA", "REINDEER", "SNOWMAN", "TINSEL", "NOEL", "BAUBLE"),
    ),
    ("seasonal.easter", ("EASTER", "BUNNY")),
    ("jewellery", ("NECKLACE", "BRACELET", "EARRING", "PENDANT", "BROOCH", "ANKLET", "CUFFLINK")),
    (
        "home.lighting",
        (
            "T-LIGHT",
            "TEALIGHT",
            "TEA LIGHT",
            "CANDLE",
            "LANTERN",
            "LAMP",
            "NIGHTLIGHT",
            "FAIRY LIGHT",
            "LIGHTS",
            "LIGHT HOLDER",
        ),
    ),
    ("bags.luggage", ("BAG", "TOTE", "PURSE", "WALLET", "SHOPPER", "BACKPACK", "SATCHEL")),
    (
        "stationery.giftwrap",
        (
            "GREETING CARD",
            "NOTEBOOK",
            "PENCIL",
            "CHALKBOARD",
            "GIFT WRAP",
            "GIFT TAG",
            "WRAP",
            "STICKER",
            "ENVELOPE",
            "JOURNAL",
            "NOTECARD",
            "POSTCARD",
        ),
    ),
    (
        "kitchen.dining",
        (
            "MUG",
            "BOWL",
            "PLATE",
            "TEAPOT",
            "JUG",
            "CUTLERY",
            "BAKING",
            "CAKE",
            "APRON",
            "TRAY",
            "COASTER",
            "EGG CUP",
            "JAR",
            "FLASK",
            "LUNCH BOX",
            "CAKE STAND",
            "TEASPOON",
            "KITCHEN",
        ),
    ),
    (
        "home.textiles",
        ("CUSHION", "TOWEL", "BLANKET", "THROW", "DOORMAT", "RUG", "APRON", "TEA TOWEL"),
    ),
    (
        "garden.outdoor",
        (
            "GARDEN",
            "PLANTER",
            "WATERING",
            "BIRDHOUSE",
            "BIRD FEEDER",
            "TROWEL",
            "FLOWERPOT",
            "PARASOL",
        ),
    ),
    (
        "toys.games",
        (
            "GAME",
            "PUZZLE",
            "JIGSAW",
            "DOLL",
            "PLAYHOUSE",
            "SKIPPING",
            "SPINNING TOP",
            "BINGO",
            "TOY",
            "SOLDIER",
        ),
    ),
    (
        "party.celebration",
        ("PARTY", "BALLOON", "BUNTING", "CONFETTI", "CAKE CASE", "PLACEMAT", "GARLAND"),
    ),
    (
        "craft.hobby",
        ("CRAFT", "SEWING", "RIBBON", "FELT KIT", "BEADS", "KNITTING", "EMBROIDERY", "PAINT"),
    ),
    ("bathroom", ("SOAP", "BATH", "TOOTHBRUSH", "FLANNEL")),
    (
        "home.storage",
        (
            "BOX",
            "TIN",
            "BASKET",
            "CRATE",
            "RACK",
            "DRAWER",
            "CADDY",
            "BIN",
            "HOOK",
            "STORAGE",
            "HAMPER",
        ),
    ),
    (
        "home.decor",
        (
            "FRAME",
            "MIRROR",
            "CLOCK",
            "SIGN",
            "WALL ART",
            "VASE",
            "DECORATION",
            "HANGING",
            "ORNAMENT",
            "HEART",
            "STAR",
            "PHOTO",
            "DOORSTOP",
            "BOTTLE",
        ),
    ),
)

FALLBACK_CATEGORY = "uncategorised"

COLOURS: tuple[str, ...] = (
    "PINK",
    "BLUE",
    "RED",
    "WHITE",
    "BLACK",
    "GREEN",
    "SILVER",
    "GOLD",
    "IVORY",
    "CREAM",
    "PURPLE",
    "ORANGE",
    "YELLOW",
    "BROWN",
    "GREY",
    "GRAY",
    "TURQUOISE",
    "NAVY",
)

MATERIALS: tuple[str, ...] = (
    "GLASS",
    "METAL",
    "ZINC",
    "CERAMIC",
    "WOODEN",
    "WOOD",
    "PAPER",
    "FELT",
    "CRYSTAL",
    "ENAMEL",
    "SILK",
    "COTTON",
    "LEATHER",
    "PLASTIC",
    "WICKER",
    "JUTE",
    "TIN",
)

PATTERNS: tuple[str, ...] = (
    "RETROSPOT",
    "POLKADOT",
    "POLKA DOT",
    "FLORAL",
    "STRIPE",
    "GINGHAM",
    "VINTAGE",
    "PAISLEY",
    "SPOTTY",
)

SIZES: tuple[str, ...] = ("SMALL", "LARGE", "MINI", "JUMBO", "MEDIUM", "GIANT")

PACK_RE = re.compile(r"\b(?:SET|PACK|BOX)\s+OF\s+(\d+)\b")

#: Fields the source has no value for. Left NULL rather than invented; Module 6
#: scores their absence.
UNAVAILABLE_FIELDS: tuple[str, ...] = ("brand", "gtin", "image_url", "description")


def categorise(title: str) -> str:
    """Map a product title to a category path by first matching rule."""
    upper = title.upper()
    for path, keywords in CATEGORY_RULES:
        if any(keyword in upper for keyword in keywords):
            return path
    return FALLBACK_CATEGORY


def extract_attributes(title: str) -> dict[str, Any]:
    """Pull structured attributes out of a free-text title.

    Only returns keys it actually found, so an absent attribute stays absent
    rather than becoming an empty string that looks like real data.
    """
    upper = title.upper()
    attributes: dict[str, Any] = {}

    colours = [c for c in COLOURS if re.search(rf"\b{c}\b", upper)]
    if colours:
        # GREY/GRAY are the same colour spelled two ways.
        normalised = sorted({"GREY" if c == "GRAY" else c for c in colours})
        attributes["colour"] = [c.title() for c in normalised]

    materials = [m for m in MATERIALS if re.search(rf"\b{m}\b", upper)]
    if materials:
        attributes["material"] = sorted({m.title() for m in materials})

    patterns = [p for p in PATTERNS if p in upper]
    if patterns:
        attributes["pattern"] = sorted({p.title() for p in patterns})

    sizes = [s for s in SIZES if re.search(rf"\b{s}\b", upper)]
    if sizes:
        attributes["size"] = sizes[0].title()

    pack = PACK_RE.search(upper)
    if pack:
        attributes["pack_size"] = int(pack.group(1))

    return attributes


def build_catalog(products: pd.DataFrame) -> pd.DataFrame:
    """Build catalog rows from the dataset's per-product aggregates.

    Args:
        products: One row per product with at least `product_id`, `title`, `price`.

    Returns:
        A frame matching the `products` table, with `generated_fields` naming
        every value that was derived rather than read from the source.
    """
    if products.empty:
        return pd.DataFrame(
            columns=[
                "product_id",
                "title",
                "description",
                "brand",
                "category",
                "category_path",
                "price",
                "currency",
                "image_url",
                "gtin",
                "in_stock",
                "attributes",
                "generated",
                "generated_fields",
            ]
        )

    frame = products.copy()
    frame["title"] = frame["title"].astype("string").str.strip().str.title()

    titles = frame["title"].fillna("")
    frame["category_path"] = titles.map(categorise)
    # Top-level category is the first path segment.
    frame["category"] = frame["category_path"].str.split(".").str[0]
    frame["attributes"] = titles.map(extract_attributes)

    def generated_fields(attributes: dict[str, Any]) -> list[str]:
        return ["category", "category_path", *(f"attributes.{key}" for key in sorted(attributes))]

    frame["generated_fields"] = frame["attributes"].map(generated_fields)
    # Every row has a derived category, so every row is partly generated.
    frame["generated"] = True

    frame["description"] = None
    frame["brand"] = None
    frame["gtin"] = None
    frame["image_url"] = None
    frame["currency"] = "GBP"
    frame["in_stock"] = True

    columns = [
        "product_id",
        "title",
        "description",
        "brand",
        "category",
        "category_path",
        "price",
        "currency",
        "image_url",
        "gtin",
        "in_stock",
        "attributes",
        "generated",
        "generated_fields",
    ]
    return frame[columns].reset_index(drop=True)


def coverage_report(catalog: pd.DataFrame) -> dict[str, float]:
    """Share of products carrying each field. Feeds the Phase 8 readiness score.

    Reported during ingest so the catalog's real gaps are visible immediately
    rather than discovered six phases later.
    """
    if catalog.empty:
        return {}
    total = len(catalog)
    report = {
        "title": float(catalog["title"].notna().mean()),
        "price": float(catalog["price"].notna().mean()),
        "category_derived": float((catalog["category_path"] != FALLBACK_CATEGORY).mean()),
        "brand": float(catalog["brand"].notna().mean()),
        "gtin": float(catalog["gtin"].notna().mean()),
        "image_url": float(catalog["image_url"].notna().mean()),
        "description": float(catalog["description"].notna().mean()),
        "any_attribute": float(catalog["attributes"].map(bool).sum() / total),
    }
    return {key: round(value, 4) for key, value in report.items()}
