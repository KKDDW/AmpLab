"""Geometry and component tools for COMSOL models."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Sequence, Union

from .common import (
    current_model,
    ensure_component,
    ensure_geometry,
    geometry_entity_counts,
    list_tags,
    safe_call,
    set_properties,
    to_jsonable,
    unique_tag,
)

Scalar = Union[str, int, float]


def _expr_list(values: Sequence[Scalar]) -> list[str]:
    return [str(value) for value in values]


def model_create_component(component_name: str = "comp1", model_name: Optional[str] = None) -> dict:
    """Create a model component, the container for geometry/materials/physics/mesh."""
    model, error = current_model(model_name)
    if error:
        return error
    comp, comp_error = ensure_component(model, component_name=component_name, create=True)
    if comp_error:
        return {"success": False, "error": comp_error}
    return {
        "success": True,
        "component": component_name,
        "label": safe_call(comp, "label", component_name),
        "model": safe_call(model, "name", "model"),
    }


def component_list(model_name: Optional[str] = None) -> dict:
    """List model components."""
    model, error = current_model(model_name)
    if error:
        return error
    try:
        tags = list_tags(model.java.component())
        return {"success": True, "components": tags, "count": len(tags)}
    except Exception as exc:
        return {"success": False, "error": f"Failed to list components: {exc}"}


def geometry_list(model_name: Optional[str] = None, component_name: Optional[str] = None) -> dict:
    """List geometry sequences."""
    model, error = current_model(model_name)
    if error:
        return error
    try:
        if component_name:
            comp, comp_error = ensure_component(model, component_name=component_name, create=False)
            if comp_error:
                return {"success": False, "error": comp_error}
            geometries = list_tags(comp.geom())
        else:
            geometries = to_jsonable(safe_call(model, "geometries", [])) or []
        return {"success": True, "geometries": geometries, "count": len(geometries)}
    except Exception as exc:
        return {"success": False, "error": f"Failed to list geometries: {exc}"}


def geometry_create(
    geometry_name: str = "geom1",
    space_dimension: int = 3,
    component_name: str = "comp1",
    model_name: Optional[str] = None,
) -> dict:
    """Create or return a geometry sequence."""
    if space_dimension not in {1, 2, 3}:
        return {"success": False, "error": "space_dimension must be 1, 2, or 3."}
    model, error = current_model(model_name)
    if error:
        return error
    geom, geom_error = ensure_geometry(
        model,
        component_name=component_name,
        geometry_name=geometry_name,
        space_dimension=space_dimension,
        create=True,
    )
    if geom_error:
        return {"success": False, "error": geom_error}
    return {
        "success": True,
        "geometry": geometry_name,
        "component": component_name,
        "space_dimension": space_dimension,
        "tag": safe_call(geom, "tag", geometry_name),
    }


def _feature_tag(geom: Any, feature_name: Optional[str], prefix: str) -> str:
    if feature_name:
        return feature_name
    return unique_tag(list_tags(geom.feature()), prefix)


def _create_feature(
    feature_type: str,
    feature_name: Optional[str],
    properties: dict[str, Any],
    geometry_name: str,
    component_name: str,
    space_dimension: int,
    model_name: Optional[str],
) -> dict:
    model, error = current_model(model_name)
    if error:
        return error
    geom, geom_error = ensure_geometry(
        model,
        component_name=component_name,
        geometry_name=geometry_name,
        space_dimension=space_dimension,
        create=True,
    )
    if geom_error:
        return {"success": False, "error": geom_error}
    try:
        prefix = feature_type[:3].lower()
        tag = _feature_tag(geom, feature_name, prefix)
        feature = geom.feature().create(tag, feature_type)
        property_result = set_properties(feature, properties)
        return {
            "success": True,
            "feature": {
                "tag": tag,
                "type": feature_type,
                "geometry": geometry_name,
                "component": component_name,
                "properties": properties,
                "property_result": property_result,
            },
        }
    except Exception as exc:
        return {"success": False, "error": f"Failed to create {feature_type}: {exc}"}


def geometry_add_block(
    position: Sequence[Scalar] = ("0", "0", "0"),
    size: Sequence[Scalar] = ("1", "1", "1"),
    geometry_name: str = "geom1",
    component_name: str = "comp1",
    feature_name: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Add a 3D block feature."""
    if len(position) != 3 or len(size) != 3:
        return {"success": False, "error": "Block position and size must each have 3 values."}
    return _create_feature(
        "Block",
        feature_name,
        {"pos": _expr_list(position), "size": _expr_list(size)},
        geometry_name,
        component_name,
        3,
        model_name,
    )


def geometry_add_cylinder(
    position: Sequence[Scalar] = ("0", "0", "0"),
    radius: Scalar = "0.5",
    height: Scalar = "1",
    geometry_name: str = "geom1",
    component_name: str = "comp1",
    feature_name: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Add a 3D cylinder feature."""
    if len(position) != 3:
        return {"success": False, "error": "Cylinder position must have 3 values."}
    return _create_feature(
        "Cylinder",
        feature_name,
        {"pos": _expr_list(position), "r": str(radius), "h": str(height)},
        geometry_name,
        component_name,
        3,
        model_name,
    )


def geometry_add_sphere(
    position: Sequence[Scalar] = ("0", "0", "0"),
    radius: Scalar = "0.5",
    geometry_name: str = "geom1",
    component_name: str = "comp1",
    feature_name: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Add a 3D sphere feature."""
    if len(position) != 3:
        return {"success": False, "error": "Sphere position must have 3 values."}
    return _create_feature(
        "Sphere",
        feature_name,
        {"pos": _expr_list(position), "r": str(radius)},
        geometry_name,
        component_name,
        3,
        model_name,
    )


def geometry_add_rectangle(
    position: Sequence[Scalar] = ("0", "0"),
    size: Sequence[Scalar] = ("1", "1"),
    geometry_name: str = "geom1",
    component_name: str = "comp1",
    feature_name: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Add a 2D rectangle feature."""
    if len(position) != 2 or len(size) != 2:
        return {"success": False, "error": "Rectangle position and size must each have 2 values."}
    return _create_feature(
        "Rectangle",
        feature_name,
        {"pos": _expr_list(position), "size": _expr_list(size)},
        geometry_name,
        component_name,
        2,
        model_name,
    )


def geometry_add_circle(
    position: Sequence[Scalar] = ("0", "0"),
    radius: Scalar = "0.5",
    geometry_name: str = "geom1",
    component_name: str = "comp1",
    feature_name: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Add a 2D circle feature."""
    if len(position) != 2:
        return {"success": False, "error": "Circle position must have 2 values."}
    return _create_feature(
        "Circle",
        feature_name,
        {"pos": _expr_list(position), "r": str(radius)},
        geometry_name,
        component_name,
        2,
        model_name,
    )


def geometry_boolean_union(
    input_objects: Sequence[str],
    geometry_name: str = "geom1",
    component_name: str = "comp1",
    feature_name: Optional[str] = None,
    keep_interior_boundaries: bool = True,
    model_name: Optional[str] = None,
) -> dict:
    """Create a Boolean union feature."""
    if not input_objects:
        return {"success": False, "error": "input_objects must not be empty."}
    model, error = current_model(model_name)
    if error:
        return error
    geom, geom_error = ensure_geometry(model, component_name=component_name, geometry_name=geometry_name, create=False)
    if geom_error:
        return {"success": False, "error": geom_error}
    try:
        tag = _feature_tag(geom, feature_name, "uni")
        feature = geom.feature().create(tag, "Union")
        feature.selection("input").set(list(input_objects))
        try:
            feature.set("intbnd", "on" if keep_interior_boundaries else "off")
        except Exception:
            pass
        return {
            "success": True,
            "feature": {
                "tag": tag,
                "type": "Union",
                "input_objects": list(input_objects),
                "keep_interior_boundaries": keep_interior_boundaries,
            },
        }
    except Exception as exc:
        return {"success": False, "error": f"Failed to create union: {exc}"}


def geometry_boolean_difference(
    input_objects: Sequence[str],
    objects_to_subtract: Sequence[str],
    geometry_name: str = "geom1",
    component_name: str = "comp1",
    feature_name: Optional[str] = None,
    keep_interior_boundaries: bool = True,
    model_name: Optional[str] = None,
) -> dict:
    """Create a Boolean difference feature."""
    if not input_objects or not objects_to_subtract:
        return {"success": False, "error": "input_objects and objects_to_subtract must not be empty."}
    model, error = current_model(model_name)
    if error:
        return error
    geom, geom_error = ensure_geometry(model, component_name=component_name, geometry_name=geometry_name, create=False)
    if geom_error:
        return {"success": False, "error": geom_error}
    try:
        tag = _feature_tag(geom, feature_name, "dif")
        feature = geom.feature().create(tag, "Difference")
        feature.selection("input").set(list(input_objects))
        feature.selection("input2").set(list(objects_to_subtract))
        try:
            feature.set("intbnd", "on" if keep_interior_boundaries else "off")
        except Exception:
            pass
        return {
            "success": True,
            "feature": {
                "tag": tag,
                "type": "Difference",
                "input_objects": list(input_objects),
                "objects_to_subtract": list(objects_to_subtract),
                "keep_interior_boundaries": keep_interior_boundaries,
            },
        }
    except Exception as exc:
        return {"success": False, "error": f"Failed to create difference: {exc}"}


def geometry_import(
    file_path: str,
    geometry_name: str = "geom1",
    component_name: str = "comp1",
    feature_name: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Import CAD/mesh geometry into a geometry sequence."""
    path = Path(file_path)
    if not path.exists():
        return {"success": False, "error": f"Geometry file not found: {file_path}"}
    model, error = current_model(model_name)
    if error:
        return error
    geom, geom_error = ensure_geometry(model, component_name=component_name, geometry_name=geometry_name, create=True)
    if geom_error:
        return {"success": False, "error": geom_error}
    try:
        tag = _feature_tag(geom, feature_name, "imp")
        feature = geom.feature().create(tag, "Import")
        feature.set("filename", str(path.resolve()))
        return {
            "success": True,
            "feature": {"tag": tag, "type": "Import", "file_path": str(path.resolve()), "geometry": geometry_name},
        }
    except Exception as exc:
        return {"success": False, "error": f"Failed to import geometry: {exc}"}


def geometry_build(
    geometry_name: str = "geom1",
    component_name: str = "comp1",
    model_name: Optional[str] = None,
) -> dict:
    """Build a geometry sequence."""
    model, error = current_model(model_name)
    if error:
        return error
    geom, geom_error = ensure_geometry(model, component_name=component_name, geometry_name=geometry_name, create=False)
    if geom_error:
        return {"success": False, "error": geom_error}
    try:
        geom.run()
        return {
            "success": True,
            "geometry": geometry_name,
            "component": component_name,
            "entity_counts": geometry_entity_counts(geom),
            "problems": to_jsonable(safe_call(model, "problems", [])),
        }
    except Exception as exc:
        return {"success": False, "error": f"Failed to build geometry: {exc}"}


def geometry_list_features(
    geometry_name: str = "geom1",
    component_name: str = "comp1",
    model_name: Optional[str] = None,
) -> dict:
    """List geometry features in a sequence."""
    model, error = current_model(model_name)
    if error:
        return error
    geom, geom_error = ensure_geometry(model, component_name=component_name, geometry_name=geometry_name, create=False)
    if geom_error:
        return {"success": False, "error": geom_error}
    try:
        features = []
        for tag in list_tags(geom.feature()):
            feature = geom.feature(tag)
            features.append({"tag": tag, "label": safe_call(feature, "label", tag), "type": safe_call(feature, "getType", None)})
        return {"success": True, "geometry": geometry_name, "features": features, "count": len(features)}
    except Exception as exc:
        return {"success": False, "error": f"Failed to list geometry features: {exc}"}


def geometry_get_entity_counts(
    geometry_name: str = "geom1",
    component_name: str = "comp1",
    build_first: bool = False,
    model_name: Optional[str] = None,
) -> dict:
    """Return best-effort domain/boundary/edge/point counts for a geometry."""
    model, error = current_model(model_name)
    if error:
        return error
    geom, geom_error = ensure_geometry(model, component_name=component_name, geometry_name=geometry_name, create=False)
    if geom_error:
        return {"success": False, "error": geom_error}
    try:
        if build_first:
            geom.run()
        counts = geometry_entity_counts(geom)
        return {"success": True, "geometry": geometry_name, "component": component_name, "entity_counts": counts}
    except Exception as exc:
        return {"success": False, "error": f"Failed to inspect geometry entities: {exc}"}
