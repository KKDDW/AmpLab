"""Material tools for COMSOL models."""

from __future__ import annotations

from typing import Any, Optional, Sequence

from .common import current_model, ensure_component, list_tags, safe_call, set_selection, to_jsonable, unique_tag


COMMON_MATERIALS: dict[str, dict[str, str]] = {
    "air": {"relpermittivity": "1", "thermalconductivity": "0.026[W/(m*K)]", "density": "1.225[kg/m^3]"},
    "water": {
        "relpermittivity": "80",
        "thermalconductivity": "0.6[W/(m*K)]",
        "density": "1000[kg/m^3]",
        "dynamicviscosity": "1e-3[Pa*s]",
    },
    "copper": {
        "electricconductivity": "5.998e7[S/m]",
        "thermalconductivity": "400[W/(m*K)]",
        "density": "8960[kg/m^3]",
    },
    "silicon": {
        "relpermittivity": "11.7",
        "thermalconductivity": "130[W/(m*K)]",
        "density": "2329[kg/m^3]",
        "youngsmodulus": "170e9[Pa]",
        "poissonsratio": "0.28",
    },
    "aluminum": {
        "electricconductivity": "3.774e7[S/m]",
        "thermalconductivity": "237[W/(m*K)]",
        "density": "2700[kg/m^3]",
        "youngsmodulus": "70e9[Pa]",
        "poissonsratio": "0.33",
    },
}


def material_list(model_name: Optional[str] = None, component_name: Optional[str] = None) -> dict:
    """List materials."""
    model, error = current_model(model_name)
    if error:
        return error
    try:
        if component_name:
            comp, comp_error = ensure_component(model, component_name=component_name, create=False)
            if comp_error:
                return {"success": False, "error": comp_error}
            materials = list_tags(comp.material())
        else:
            materials = to_jsonable(safe_call(model, "materials", [])) or []
        return {"success": True, "materials": materials, "count": len(materials)}
    except Exception as exc:
        return {"success": False, "error": f"Failed to list materials: {exc}"}


def material_create_blank(
    material_name: str,
    component_name: str = "comp1",
    tag: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Create an empty material in a component."""
    model, error = current_model(model_name)
    if error:
        return error
    comp, comp_error = ensure_component(model, component_name=component_name, create=True)
    if comp_error:
        return {"success": False, "error": comp_error}
    try:
        mat_tag = tag or unique_tag(list_tags(comp.material()), "mat")
        material = comp.material().create(mat_tag, "Common")
        material.label(material_name)
        return {"success": True, "material": {"tag": mat_tag, "label": material_name, "component": component_name}}
    except Exception as exc:
        return {"success": False, "error": f"Failed to create material: {exc}"}


def material_create_common(
    material_key: str,
    component_name: str = "comp1",
    tag: Optional[str] = None,
    domains: Optional[Sequence[int]] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Create one of the built-in local material presets."""
    key = material_key.strip().lower()
    if key not in COMMON_MATERIALS:
        return {"success": False, "error": f"Unknown material preset: {material_key}", "available": sorted(COMMON_MATERIALS)}
    created = material_create_blank(key.title(), component_name=component_name, tag=tag, model_name=model_name)
    if not created.get("success"):
        return created
    mat_tag = created["material"]["tag"]
    properties = COMMON_MATERIALS[key]
    set_result = material_set_property(mat_tag, properties=properties, component_name=component_name, model_name=model_name)
    assign_result = None
    if domains:
        assign_result = material_assign_domains(mat_tag, domains=domains, component_name=component_name, model_name=model_name)
    return {
        "success": bool(set_result.get("success")) and (assign_result is None or bool(assign_result.get("success"))),
        "material": created["material"],
        "preset": key,
        "properties": properties,
        "set_result": set_result,
        "assign_result": assign_result,
    }


def _get_material(model: Any, material_tag: str, component_name: str) -> tuple[Any, Optional[str]]:
    comp, error = ensure_component(model, component_name=component_name, create=False)
    if error:
        return None, error
    try:
        material = comp.material(material_tag)
        if material is not None:
            return material, None
    except Exception:
        pass
    try:
        for tag in list_tags(comp.material()):
            material = comp.material(tag)
            label = str(safe_call(material, "label", ""))
            if material_tag in {tag, label}:
                return material, None
    except Exception:
        pass
    return None, f"Material '{material_tag}' not found in component '{component_name}'."


def material_set_property(
    material_tag: str,
    properties: Optional[dict[str, Any]] = None,
    property_name: Optional[str] = None,
    value: Optional[Any] = None,
    component_name: str = "comp1",
    model_name: Optional[str] = None,
) -> dict:
    """Set one or more material properties."""
    merged = dict(properties or {})
    if property_name:
        merged[property_name] = value
    if not merged:
        return {"success": False, "error": "Provide properties or property_name/value."}
    model, error = current_model(model_name)
    if error:
        return error
    material, mat_error = _get_material(model, material_tag, component_name)
    if mat_error:
        return {"success": False, "error": mat_error}
    applied: dict[str, Any] = {}
    failed: dict[str, str] = {}
    try:
        property_group = material.propertyGroup("def")
        for name, prop_value in merged.items():
            try:
                property_group.set(name, prop_value)
                applied[name] = to_jsonable(prop_value)
            except Exception as exc:
                failed[name] = str(exc)
        return {"success": not failed, "material": material_tag, "applied": applied, "failed": failed}
    except Exception as exc:
        return {"success": False, "error": f"Failed to set material property: {exc}"}


def material_assign_domains(
    material_tag: str,
    domains: Sequence[int],
    component_name: str = "comp1",
    model_name: Optional[str] = None,
) -> dict:
    """Assign a material to domain entity numbers."""
    if not domains:
        return {"success": False, "error": "domains must not be empty."}
    model, error = current_model(model_name)
    if error:
        return error
    material, mat_error = _get_material(model, material_tag, component_name)
    if mat_error:
        return {"success": False, "error": mat_error}
    selection = set_selection(material, domains)
    return {
        "success": "error" not in selection,
        "material": material_tag,
        "component": component_name,
        "selection": selection,
    }


def material_info(material_tag: str, component_name: str = "comp1", model_name: Optional[str] = None) -> dict:
    """Return best-effort metadata for a material."""
    model, error = current_model(model_name)
    if error:
        return error
    material, mat_error = _get_material(model, material_tag, component_name)
    if mat_error:
        return {"success": False, "error": mat_error}
    info = {"tag": material_tag, "label": safe_call(material, "label", material_tag), "component": component_name}
    try:
        info["selection"] = to_jsonable(material.selection().entities())
    except Exception:
        pass
    try:
        info["property_groups"] = list_tags(material.propertyGroup())
    except Exception:
        pass
    return {"success": True, "material": info}
