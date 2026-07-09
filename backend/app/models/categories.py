"""Input category rules."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DataKind(str, Enum):
    raster = "raster"
    vector = "vector"
    table = "table"


class InputCategory(str, Enum):
    dem = "dem"
    fire_perimeter = "fire_perimeter"
    burn_severity = "burn_severity"
    land_cover = "land_cover"
    hydrologic_soil_group = "hydrologic_soil_group"
    rainfall = "rainfall"
    water_body = "water_body"
    hydrography = "hydrography"


@dataclass(frozen=True)
class CategoryRule:
    label: str
    kinds: tuple[DataKind, ...]
    extensions: tuple[str, ...]
    required_for_preprocess: bool = False
    required_for_model: bool = False
    required_attributes: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    categorical: bool = False


CATEGORY_RULES: dict[InputCategory, CategoryRule] = {
    InputCategory.dem: CategoryRule(
        label="DEM raster",
        kinds=(DataKind.raster,),
        extensions=(".tif", ".tiff"),
        required_for_preprocess=True,
        required_for_model=True,
    ),
    InputCategory.fire_perimeter: CategoryRule(
        label="Burned area or fire perimeter vector",
        kinds=(DataKind.vector,),
        extensions=(".gpkg", ".geojson", ".zip"),
        required_for_preprocess=True,
        required_for_model=True,
    ),
    InputCategory.burn_severity: CategoryRule(
        label="Burn severity raster or vector",
        kinds=(DataKind.raster, DataKind.vector),
        extensions=(".tif", ".tiff", ".gpkg", ".geojson", ".zip"),
        required_for_preprocess=True,
        required_for_model=True,
        required_attributes=("burn_class",),
        aliases=("burn_class", "burn_severity", "severity", "dnbr_class", "soil_burn_severity"),
        categorical=True,
    ),
    InputCategory.land_cover: CategoryRule(
        label="Land cover raster or vector",
        kinds=(DataKind.raster, DataKind.vector),
        extensions=(".tif", ".tiff", ".gpkg", ".geojson", ".zip"),
        required_for_preprocess=True,
        required_for_model=True,
        required_attributes=("landcover_class",),
        aliases=("landcover_class", "land_cover", "landcover", "class", "lc_class"),
        categorical=True,
    ),
    InputCategory.hydrologic_soil_group: CategoryRule(
        label="Hydrologic soil group raster or vector",
        kinds=(DataKind.raster, DataKind.vector),
        extensions=(".tif", ".tiff", ".gpkg", ".geojson", ".zip"),
        required_for_preprocess=False,
        required_for_model=True,
        required_attributes=("hsg",),
        aliases=("hsg", "hydrologic_soil_group", "soil_group", "soil_hsg"),
        categorical=True,
    ),
    InputCategory.rainfall: CategoryRule(
        label="Rainfall event CSV",
        kinds=(DataKind.table,),
        extensions=(".csv",),
        required_for_preprocess=True,
        required_for_model=True,
    ),
    InputCategory.water_body: CategoryRule(
        label="Lake or water body vector",
        kinds=(DataKind.vector,),
        extensions=(".gpkg", ".geojson", ".zip"),
    ),
    InputCategory.hydrography: CategoryRule(
        label="Hydrography vector",
        kinds=(DataKind.vector,),
        extensions=(".gpkg", ".geojson", ".zip"),
    ),
}


def category_from_string(value: str) -> InputCategory:
    try:
        return InputCategory(value)
    except ValueError as exc:
        allowed = ", ".join(c.value for c in InputCategory)
        raise ValueError(f"Unknown input category '{value}'. Allowed: {allowed}") from exc


def accepted_extensions(category: InputCategory) -> tuple[str, ...]:
    return CATEGORY_RULES[category].extensions
