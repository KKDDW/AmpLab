"""Boundary condition tools for COMSOL physics interfaces."""

from __future__ import annotations

from typing import Any, Optional, Sequence

from .common import current_model, get_physics, list_tags, set_properties, set_selection, unique_tag


BOUNDARY_PRESETS: dict[str, dict[str, Any]] = {
    "electrostatics_ground": {"physics_tag": "es", "condition_type": "Ground", "properties": {}},
    "electrostatics_potential": {"physics_tag": "es", "condition_type": "ElectricPotential", "properties": {"V0": "1[V]"}},
    "electrostatics_terminal": {"physics_tag": "es", "condition_type": "Terminal", "properties": {"V0": "1[V]"}},
    "heat_temperature": {"physics_tag": "ht", "condition_type": "TemperatureBoundary", "properties": {"T0": "293.15[K]"}},
    "heat_flux": {"physics_tag": "ht", "condition_type": "HeatFluxBoundary", "properties": {"q0": "1e3[W/m^2]"}},
    "heat_convection": {
        "physics_tag": "ht",
        "condition_type": "ConvectiveHeatFlux",
        "properties": {"h": "10[W/(m^2*K)]", "Text": "293.15[K]"},
    },
    "flow_inlet": {"physics_tag": "spf", "condition_type": "InletBoundary", "properties": {"U0": "1[m/s]"}},
    "flow_outlet": {"physics_tag": "spf", "condition_type": "OutletBoundary", "properties": {"p0": "0[Pa]"}},
    "solid_fixed": {"physics_tag": "solid", "condition_type": "Fixed", "properties": {}},
    "solid_boundary_load": {"physics_tag": "solid", "condition_type": "BoundaryLoad", "properties": {"FperArea": "1[MPa]"}},
}


def boundary_get_presets() -> dict:
    """Return built-in boundary condition presets."""
    return {"success": True, "presets": BOUNDARY_PRESETS, "count": len(BOUNDARY_PRESETS)}


def boundary_add_condition(
    physics_tag: str,
    condition_type: str,
    boundaries: Optional[Sequence[int]] = None,
    properties: Optional[dict[str, Any]] = None,
    feature_tag: Optional[str] = None,
    component_name: Optional[str] = None,
    named_selection: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Add a boundary condition feature to an existing physics interface."""
    if not boundaries and not named_selection:
        return {"success": False, "error": "Provide boundaries or named_selection."}
    model, error = current_model(model_name)
    if error:
        return error
    physics, physics_error = get_physics(model, physics_tag, component_name)
    if physics_error:
        return {"success": False, "error": physics_error}
    try:
        existing = list_tags(physics.feature())
        tag = feature_tag or unique_tag(existing, _prefix_for_condition(condition_type))
        feature = physics.feature().create(tag, condition_type, 2)
        selection = set_selection(feature, boundaries, named_selection=named_selection)
        prop_result = set_properties(feature, properties)
        return {
            "success": "error" not in selection and not prop_result["failed"],
            "boundary_condition": {
                "tag": tag,
                "type": condition_type,
                "physics": physics_tag,
                "boundaries": [int(boundary) for boundary in boundaries] if boundaries else [],
                "named_selection": named_selection,
                "properties": properties or {},
                "selection": selection,
                "property_result": prop_result,
            },
        }
    except Exception as exc:
        return {"success": False, "error": f"Failed to add boundary condition: {exc}"}


def boundary_add_preset(
    preset_name: str,
    boundaries: Optional[Sequence[int]] = None,
    properties: Optional[dict[str, Any]] = None,
    feature_tag: Optional[str] = None,
    component_name: Optional[str] = None,
    named_selection: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Add one of the built-in boundary condition presets."""
    preset = BOUNDARY_PRESETS.get(preset_name)
    if preset is None:
        return {"success": False, "error": f"Unknown boundary preset: {preset_name}", "available": sorted(BOUNDARY_PRESETS)}
    merged = dict(preset["properties"])
    merged.update(properties or {})
    result = boundary_add_condition(
        physics_tag=preset["physics_tag"],
        condition_type=preset["condition_type"],
        boundaries=boundaries,
        properties=merged,
        feature_tag=feature_tag,
        component_name=component_name,
        named_selection=named_selection,
        model_name=model_name,
    )
    result["preset"] = preset_name
    return result


def boundary_list_conditions(
    physics_tag: str,
    component_name: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """List boundary/domain features under a physics interface."""
    model, error = current_model(model_name)
    if error:
        return error
    physics, physics_error = get_physics(model, physics_tag, component_name)
    if physics_error:
        return {"success": False, "error": physics_error}
    try:
        conditions = []
        for tag in list_tags(physics.feature()):
            feature = physics.feature(tag)
            item = {"tag": tag}
            for method, key in [("label", "label"), ("getType", "type")]:
                try:
                    item[key] = getattr(feature, method)()
                except Exception:
                    pass
            try:
                item["selection"] = list(feature.selection().entities())
            except Exception:
                pass
            conditions.append(item)
        return {"success": True, "physics": physics_tag, "conditions": conditions, "count": len(conditions)}
    except Exception as exc:
        return {"success": False, "error": f"Failed to list boundary conditions: {exc}"}


def boundary_remove_condition(
    physics_tag: str,
    feature_tag: str,
    component_name: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Remove a boundary condition feature."""
    model, error = current_model(model_name)
    if error:
        return error
    physics, physics_error = get_physics(model, physics_tag, component_name)
    if physics_error:
        return {"success": False, "error": physics_error}
    try:
        physics.feature().remove(feature_tag)
        return {"success": True, "physics": physics_tag, "removed": feature_tag}
    except Exception as exc:
        return {"success": False, "error": f"Failed to remove boundary condition: {exc}"}


def _prefix_for_condition(condition_type: str) -> str:
    letters = "".join(ch.lower() for ch in condition_type if ch.isalpha())
    if not letters:
        return "bc"
    if letters.startswith("electricpotential"):
        return "pot"
    if letters.startswith("temperature"):
        return "temp"
    if letters.startswith("heatflux"):
        return "hf"
    if letters.startswith("convective"):
        return "conv"
    if letters.startswith("inlet"):
        return "inl"
    if letters.startswith("outlet"):
        return "out"
    if letters.startswith("boundaryload"):
        return "load"
    return letters[:4]
