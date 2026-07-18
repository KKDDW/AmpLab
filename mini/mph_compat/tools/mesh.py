"""Mesh tools for COMSOL models."""

from __future__ import annotations

from typing import Any, Optional, Sequence

from .common import current_model, ensure_mesh, list_tags, safe_call, set_selection, to_jsonable, unique_tag


def mesh_list(model_name: Optional[str] = None, component_name: Optional[str] = None) -> dict:
    """List mesh sequences."""
    model, error = current_model(model_name)
    if error:
        return error
    try:
        if component_name:
            mesh, mesh_error = ensure_mesh(model, component_name=component_name, create=False)
            if mesh_error:
                return {"success": False, "error": mesh_error}
            meshes = [safe_call(mesh, "tag", "mesh1")]
        else:
            meshes = to_jsonable(safe_call(model, "meshes", [])) or []
        return {"success": True, "meshes": meshes, "count": len(meshes)}
    except Exception as exc:
        return {"success": False, "error": f"Failed to list meshes: {exc}"}


def mesh_create(
    mesh_name: str = "mesh1",
    component_name: str = "comp1",
    model_name: Optional[str] = None,
) -> dict:
    """Create or return a mesh sequence."""
    model, error = current_model(model_name)
    if error:
        return error
    mesh, mesh_error = ensure_mesh(model, component_name=component_name, mesh_name=mesh_name, create=True)
    if mesh_error:
        return {"success": False, "error": mesh_error}
    return {"success": True, "mesh": mesh_name, "component": component_name, "tag": safe_call(mesh, "tag", mesh_name)}


def mesh_add_size(
    mesh_name: str = "mesh1",
    component_name: str = "comp1",
    feature_tag: Optional[str] = None,
    size: str = "normal",
    custom_properties: Optional[dict[str, Any]] = None,
    domains: Optional[Sequence[int]] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Add a mesh Size feature."""
    model, error = current_model(model_name)
    if error:
        return error
    mesh, mesh_error = ensure_mesh(model, component_name=component_name, mesh_name=mesh_name, create=True)
    if mesh_error:
        return {"success": False, "error": mesh_error}
    try:
        tag = feature_tag or unique_tag(list_tags(mesh.feature()), "size")
        feature = mesh.feature().create(tag, "Size")
        if size:
            feature.set("hauto", _size_to_hauto(size))
        for name, value in (custom_properties or {}).items():
            feature.set(name, value)
        selection = set_selection(feature, domains) if domains else {"type": "all", "selection": []}
        return {"success": True, "feature": {"tag": tag, "type": "Size", "size": size, "selection": selection}}
    except Exception as exc:
        return {"success": False, "error": f"Failed to add mesh size: {exc}"}


def mesh_add_free_tetrahedral(
    mesh_name: str = "mesh1",
    component_name: str = "comp1",
    feature_tag: Optional[str] = None,
    domains: Optional[Sequence[int]] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Add a Free Tetrahedral mesh feature."""
    return _mesh_add_feature("FreeTet", mesh_name, component_name, feature_tag, domains, model_name)


def mesh_add_free_triangular(
    mesh_name: str = "mesh1",
    component_name: str = "comp1",
    feature_tag: Optional[str] = None,
    domains: Optional[Sequence[int]] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Add a Free Triangular mesh feature."""
    return _mesh_add_feature("FreeTri", mesh_name, component_name, feature_tag, domains, model_name)


def _mesh_add_feature(
    feature_type: str,
    mesh_name: str,
    component_name: str,
    feature_tag: Optional[str],
    domains: Optional[Sequence[int]],
    model_name: Optional[str],
) -> dict:
    model, error = current_model(model_name)
    if error:
        return error
    mesh, mesh_error = ensure_mesh(model, component_name=component_name, mesh_name=mesh_name, create=True)
    if mesh_error:
        return {"success": False, "error": mesh_error}
    try:
        tag = feature_tag or unique_tag(list_tags(mesh.feature()), "ftet" if feature_type == "FreeTet" else "ftri")
        feature = mesh.feature().create(tag, feature_type)
        selection = set_selection(feature, domains) if domains else {"type": "all", "selection": []}
        return {"success": True, "feature": {"tag": tag, "type": feature_type, "mesh": mesh_name, "selection": selection}}
    except Exception as exc:
        return {"success": False, "error": f"Failed to add mesh feature {feature_type}: {exc}"}


def mesh_build(
    mesh_name: str = "mesh1",
    component_name: str = "comp1",
    model_name: Optional[str] = None,
) -> dict:
    """Build a mesh sequence."""
    model, error = current_model(model_name)
    if error:
        return error
    mesh, mesh_error = ensure_mesh(model, component_name=component_name, mesh_name=mesh_name, create=False)
    if mesh_error:
        return {"success": False, "error": mesh_error}
    try:
        mesh.run()
        return {"success": True, "mesh": mesh_name, "component": component_name, "info": _mesh_info(mesh), "problems": to_jsonable(safe_call(model, "problems", []))}
    except Exception as exc:
        return {"success": False, "error": f"Failed to build mesh: {exc}"}


def mesh_info(mesh_name: str = "mesh1", component_name: str = "comp1", model_name: Optional[str] = None) -> dict:
    """Return mesh feature and statistics information."""
    model, error = current_model(model_name)
    if error:
        return error
    mesh, mesh_error = ensure_mesh(model, component_name=component_name, mesh_name=mesh_name, create=False)
    if mesh_error:
        return {"success": False, "error": mesh_error}
    return {"success": True, "mesh": mesh_name, "component": component_name, "info": _mesh_info(mesh)}


def _mesh_info(mesh: Any) -> dict:
    info: dict[str, Any] = {"features": []}
    for tag in list_tags(mesh.feature()):
        feature = mesh.feature(tag)
        info["features"].append({"tag": tag, "label": safe_call(feature, "label", tag), "type": safe_call(feature, "getType", None)})
    for attr, key in [("getNumElem", "elements"), ("getNumVertex", "vertices")]:
        try:
            info[key] = getattr(mesh, attr)()
        except Exception:
            pass
    return to_jsonable(info)


def _size_to_hauto(size: str) -> str:
    mapping = {
        "extremely_fine": "1",
        "extra_fine": "2",
        "finer": "3",
        "fine": "4",
        "normal": "5",
        "coarse": "6",
        "coarser": "7",
        "extra_coarse": "8",
        "extremely_coarse": "9",
    }
    return mapping.get(size.strip().lower(), size)
