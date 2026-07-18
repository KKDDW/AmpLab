"""Selection tools for stable COMSOL entity targeting."""

from __future__ import annotations

from typing import Any, Optional, Sequence, Union

from .common import current_model, ensure_component, list_tags, safe_call, set_properties, set_selection, to_jsonable, unique_tag


def selection_list(component_name: str = "comp1", model_name: Optional[str] = None) -> dict:
    """List component selections with best-effort entity metadata."""
    model, error = current_model(model_name)
    if error:
        return error
    comp, comp_error = ensure_component(model, component_name=component_name, create=False)
    if comp_error:
        return {"success": False, "error": comp_error}
    try:
        selections = []
        for tag in list_tags(comp.selection()):
            selection = comp.selection(tag)
            item = {
                "tag": tag,
                "label": safe_call(selection, "label", tag),
                "type": safe_call(selection, "getType", None),
            }
            try:
                item["entities"] = to_jsonable(selection.entities())
            except Exception:
                pass
            selections.append(item)
        return {"success": True, "component": component_name, "selections": selections, "count": len(selections)}
    except Exception as exc:
        return {"success": False, "error": f"Failed to list selections: {exc}"}


def selection_create_explicit(
    selection_name: Optional[str] = None,
    entity_dimension: int = 2,
    entities: Optional[Sequence[int]] = None,
    component_name: str = "comp1",
    tag: Optional[str] = None,
    label: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Create an explicit named selection for domains, boundaries, edges, or points."""
    if entity_dimension not in {0, 1, 2, 3}:
        return {"success": False, "error": "entity_dimension must be one of 0, 1, 2, or 3."}
    if not entities:
        return {"success": False, "error": "entities must not be empty for an explicit selection."}
    model, error = current_model(model_name)
    if error:
        return error
    comp, comp_error = ensure_component(model, component_name=component_name, create=False)
    if comp_error:
        return {"success": False, "error": comp_error}
    try:
        sel_tag = tag or unique_tag(list_tags(comp.selection()), "sel")
        selection = comp.selection().create(sel_tag, "Explicit")
        try:
            selection.geom(entity_dimension)
        except Exception:
            try:
                selection.geom("geom1", entity_dimension)
            except Exception:
                pass
        if selection_name or label:
            selection.label(label or selection_name or sel_tag)
        select_result = set_selection(selection, entities)
        return {
            "success": "error" not in select_result,
            "selection": {
                "tag": sel_tag,
                "label": safe_call(selection, "label", label or selection_name or sel_tag),
                "type": "Explicit",
                "entity_dimension": entity_dimension,
                "entities": [int(entity) for entity in entities],
                "selection_result": select_result,
            },
        }
    except Exception as exc:
        return {"success": False, "error": f"Failed to create explicit selection: {exc}"}


def selection_create_box(
    selection_name: Optional[str] = None,
    entity_dimension: int = 2,
    xmin: Union[str, int, float] = "-inf",
    xmax: Union[str, int, float] = "inf",
    ymin: Union[str, int, float] = "-inf",
    ymax: Union[str, int, float] = "inf",
    zmin: Union[str, int, float] = "-inf",
    zmax: Union[str, int, float] = "inf",
    component_name: str = "comp1",
    tag: Optional[str] = None,
    label: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Create a box selection using coordinate bounds."""
    return _create_coordinate_selection(
        selection_type="Box",
        selection_name=selection_name,
        entity_dimension=entity_dimension,
        properties={"xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax, "zmin": zmin, "zmax": zmax},
        component_name=component_name,
        tag=tag,
        label=label,
        model_name=model_name,
    )


def selection_create_cylinder(
    selection_name: Optional[str] = None,
    entity_dimension: int = 2,
    axis: str = "z",
    radius: Union[str, int, float] = "1",
    x: Union[str, int, float] = "0",
    y: Union[str, int, float] = "0",
    zmin: Union[str, int, float] = "-inf",
    zmax: Union[str, int, float] = "inf",
    component_name: str = "comp1",
    tag: Optional[str] = None,
    label: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Create a cylinder selection for axis-aligned cylindrical regions."""
    if axis not in {"x", "y", "z"}:
        return {"success": False, "error": "axis must be 'x', 'y', or 'z'."}
    return _create_coordinate_selection(
        selection_type="Cylinder",
        selection_name=selection_name,
        entity_dimension=entity_dimension,
        properties={"axis": axis, "r": radius, "x": x, "y": y, "zmin": zmin, "zmax": zmax},
        component_name=component_name,
        tag=tag,
        label=label,
        model_name=model_name,
    )


def selection_inspect_entities(
    selection_tag: str,
    component_name: str = "comp1",
    model_name: Optional[str] = None,
) -> dict:
    """Inspect entities resolved by a named selection."""
    if not selection_tag:
        return {"success": False, "error": "selection_tag must not be empty."}
    model, error = current_model(model_name)
    if error:
        return error
    comp, comp_error = ensure_component(model, component_name=component_name, create=False)
    if comp_error:
        return {"success": False, "error": comp_error}
    try:
        selection = comp.selection(selection_tag)
        if selection is None:
            return {"success": False, "error": f"Selection '{selection_tag}' not found in component '{component_name}'."}
        entities = []
        try:
            entities = to_jsonable(selection.entities())
        except Exception:
            pass
        return {
            "success": True,
            "component": component_name,
            "selection": {
                "tag": selection_tag,
                "label": safe_call(selection, "label", selection_tag),
                "type": safe_call(selection, "getType", None),
                "entities": entities,
                "entity_count": len(entities) if isinstance(entities, list) else None,
            },
        }
    except Exception as exc:
        return {"success": False, "error": f"Failed to inspect selection: {exc}"}


def _create_coordinate_selection(
    selection_type: str,
    selection_name: Optional[str],
    entity_dimension: int,
    properties: dict[str, Any],
    component_name: str,
    tag: Optional[str],
    label: Optional[str],
    model_name: Optional[str],
) -> dict:
    if entity_dimension not in {0, 1, 2, 3}:
        return {"success": False, "error": "entity_dimension must be one of 0, 1, 2, or 3."}
    model, error = current_model(model_name)
    if error:
        return error
    comp, comp_error = ensure_component(model, component_name=component_name, create=False)
    if comp_error:
        return {"success": False, "error": comp_error}
    try:
        sel_tag = tag or unique_tag(list_tags(comp.selection()), "sel")
        selection = comp.selection().create(sel_tag, selection_type)
        try:
            selection.geom(entity_dimension)
        except Exception:
            try:
                selection.geom("geom1", entity_dimension)
            except Exception:
                pass
        if selection_name or label:
            selection.label(label or selection_name or sel_tag)
        prop_result = set_properties(selection, properties)
        return {
            "success": not prop_result["failed"],
            "selection": {
                "tag": sel_tag,
                "label": safe_call(selection, "label", label or selection_name or sel_tag),
                "type": selection_type,
                "entity_dimension": entity_dimension,
                "properties": properties,
                "property_result": prop_result,
            },
        }
    except Exception as exc:
        return {"success": False, "error": f"Failed to create {selection_type.lower()} selection: {exc}"}
