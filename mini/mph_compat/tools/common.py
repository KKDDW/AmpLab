"""Shared helpers for COMSOL Java API tool wrappers."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any, Optional, Sequence

from ..backends import mph_backend


def current_model(model_name: Optional[str] = None) -> tuple[Any, Optional[dict]]:
    """Return the current mph model or a standard error payload."""
    model = mph_backend.session.get_model(model_name)
    if model is None:
        return None, {"success": False, "error": f"Model not found: {model_name or 'current model'}"}
    return model, None


def safe_call(obj: Any, method: str, default: Any = None, *args: Any, **kwargs: Any) -> Any:
    try:
        func = getattr(obj, method)
        return func(*args, **kwargs)
    except Exception:
        return default


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return float(value)
    except Exception:
        return str(value)


def list_tags(container: Any) -> list[str]:
    """Best-effort tag listing for COMSOL Java collection-like objects."""
    if container is None:
        return []
    try:
        tags = container.tags()
        return [str(tag) for tag in tags]
    except Exception:
        pass
    try:
        return [str(item.tag()) for item in container]
    except Exception:
        pass
    try:
        return [str(container.get(i).tag()) for i in range(container.size())]
    except Exception:
        return []


def node_label(node: Any, default: str = "") -> str:
    """Return a COMSOL node label without raising."""
    return str(safe_call(node, "label", default) or default)


def resolve_collection_node(getter: Any, name: str) -> tuple[Any, Optional[str]]:
    """Resolve a Java collection item by tag first, then by displayed label."""
    try:
        node = getter(name)
        if node is not None:
            return node, str(safe_call(node, "tag", name) or name)
    except Exception:
        pass
    try:
        collection = getter()
    except Exception:
        collection = None
    for tag in list_tags(collection):
        try:
            node = getter(tag)
        except Exception:
            continue
        if name in {tag, node_label(node, tag)}:
            return node, tag
    return None, None


def ensure_component(model: Any, component_name: str = "comp1", create: bool = True) -> tuple[Any, Optional[str]]:
    try:
        comp, _tag = resolve_collection_node(model.java.component, component_name)
        if comp is not None:
            return comp, None
    except Exception:
        pass
    if not create:
        return None, f"Component '{component_name}' not found."
    try:
        return model.java.component().create(component_name, True), None
    except Exception as exc:
        return None, f"Failed to create component '{component_name}': {exc}"


def ensure_geometry(
    model: Any,
    component_name: str = "comp1",
    geometry_name: str = "geom1",
    space_dimension: int = 3,
    create: bool = True,
) -> tuple[Any, Optional[str]]:
    comp, error = ensure_component(model, component_name=component_name, create=create)
    if error:
        return None, error
    try:
        geom, _tag = resolve_collection_node(comp.geom, geometry_name)
        if geom is not None:
            return geom, None
    except Exception:
        pass
    if not create:
        return None, f"Geometry '{geometry_name}' not found in component '{component_name}'."
    try:
        return comp.geom().create(geometry_name, space_dimension), None
    except Exception as exc:
        return None, f"Failed to create geometry '{geometry_name}': {exc}"


def ensure_mesh(model: Any, component_name: str = "comp1", mesh_name: str = "mesh1", create: bool = True) -> tuple[Any, Optional[str]]:
    comp, error = ensure_component(model, component_name=component_name, create=create)
    if error:
        return None, error
    try:
        mesh = comp.mesh(mesh_name)
        if mesh is not None:
            return mesh, None
    except Exception:
        pass
    if not create:
        return None, f"Mesh '{mesh_name}' not found in component '{component_name}'."
    try:
        return comp.mesh().create(mesh_name), None
    except Exception as exc:
        return None, f"Failed to create mesh '{mesh_name}': {exc}"


def ensure_study(model: Any, study_name: str = "std1", create: bool = True) -> tuple[Any, Optional[str]]:
    try:
        study = model.java.study(study_name)
        if study is not None:
            return study, None
    except Exception:
        pass
    if not create:
        return None, f"Study '{study_name}' not found."
    try:
        return model.java.study().create(study_name), None
    except Exception as exc:
        return None, f"Failed to create study '{study_name}': {exc}"


def get_physics(model: Any, physics_tag: str, component_name: Optional[str] = None) -> tuple[Any, Optional[str]]:
    components: list[Any] = []
    if component_name:
        comp, error = ensure_component(model, component_name=component_name, create=False)
        if error:
            return None, error
        components = [comp]
    else:
        try:
            components = [model.java.component(tag) for tag in list_tags(model.java.component())]
        except Exception:
            components = []
    for comp in components:
        try:
            physics = comp.physics(physics_tag)
            if physics is not None:
                return physics, None
        except Exception:
            pass
        try:
            for tag in list_tags(comp.physics()):
                physics = comp.physics(tag)
                label = str(safe_call(physics, "label", ""))
                if physics_tag in {tag, label}:
                    return physics, None
        except Exception:
            pass
    return None, f"Physics interface '{physics_tag}' not found."


def set_properties(node: Any, properties: Optional[dict[str, Any]]) -> dict:
    applied: dict[str, Any] = {}
    failed: dict[str, str] = {}
    for name, value in (properties or {}).items():
        try:
            node.set(name, value)
            applied[name] = to_jsonable(value)
        except Exception as exc:
            failed[name] = str(exc)
    return {"applied": applied, "failed": failed}


def normalize_int_selection(values: Optional[Sequence[int]]) -> list[int]:
    if values is None:
        return []
    return [int(value) for value in values]


def set_selection(node: Any, entity_numbers: Optional[Sequence[int]], named_selection: Optional[str] = None) -> dict:
    if named_selection:
        try:
            node.selection().named(named_selection)
            return {"type": "named", "selection": named_selection}
        except Exception as exc:
            return {"type": "named", "selection": named_selection, "error": str(exc)}
    numbers = normalize_int_selection(entity_numbers)
    if not numbers:
        return {"type": "all", "selection": []}
    try:
        node.selection().set(numbers)
        return {"type": "explicit", "selection": numbers}
    except Exception as exc:
        return {"type": "explicit", "selection": numbers, "error": str(exc)}


def unique_tag(existing: Iterable[str], prefix: str) -> str:
    used = set(existing)
    index = 1
    while f"{prefix}{index}" in used:
        index += 1
    return f"{prefix}{index}"


def valid_tag(tag: str) -> bool:
    return bool(re.match(r"^[A-Za-z_]\w*$", tag or ""))


def geometry_entity_counts(geom: Any) -> dict:
    try:
        info = geom.info()
        return {
            "domains": to_jsonable(getattr(info, "ndomain", None)),
            "boundaries": to_jsonable(getattr(info, "nboundary", None)),
            "edges": to_jsonable(getattr(info, "nedge", None)),
            "points": to_jsonable(getattr(info, "npoint", None)),
        }
    except Exception:
        return {}
