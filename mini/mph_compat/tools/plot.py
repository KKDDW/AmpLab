"""mph-backed plot and image export tools."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..backends import mph_backend
from ..config import MODELS_DIR
from .common import current_model, list_tags, safe_call, set_properties, to_jsonable, unique_tag


def plot_list(model_name: Optional[str] = None) -> dict:
    """List result plot groups and export nodes."""
    model, error = current_model(model_name)
    if error:
        return error
    try:
        plot_groups = []
        try:
            result = model.java.result()
            tags = list_tags(result)
            if not tags:
                try:
                    tags = [str(tag) for tag in result.tags()]
                except Exception:
                    tags = []
            for tag in tags:
                node = result(tag)
                plot_groups.append(
                    {
                        "tag": tag,
                        "label": safe_call(node, "label", tag),
                        "type": safe_call(node, "getType", None),
                        "features": list_tags(safe_call(node, "feature", None)),
                    }
                )
        except Exception:
            plot_groups = to_jsonable(safe_call(model, "plots", [])) or []
        exports = []
        try:
            export_container = model.java.result().export()
            for tag in list_tags(export_container):
                export = export_container(tag)
                exports.append({"tag": tag, "label": safe_call(export, "label", tag), "type": safe_call(export, "getType", None)})
        except Exception:
            exports = to_jsonable(safe_call(model, "exports", [])) or []
        return {"success": True, "plot_groups": plot_groups, "exports": exports, "count": len(plot_groups)}
    except Exception as exc:
        return {"success": False, "error": f"Failed to list plots: {exc}"}


def plot_export_image(
    plot_group: Optional[str] = None,
    file_path: Optional[str] = None,
    width: int = 1200,
    height: int = 900,
    model_name: Optional[str] = None,
) -> dict:
    """Export a result plot group to an image file."""
    if width <= 0 or height <= 0:
        return {"success": False, "error": "width and height must be positive."}
    model, error = current_model(model_name)
    if error:
        return error
    target = _default_plot_path(file_path, "plot_export.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        plot_group = _resolve_plot_group_tag(model, plot_group)
        if plot_group:
            export = _create_image_export(model, plot_group, target, width, height)
            return {
                "success": target.exists() and target.stat().st_size > 0,
                "file": str(target),
                "plot_group": plot_group,
                "export": export,
                "file_size": target.stat().st_size if target.exists() else 0,
            }
        backend_result = mph_backend.results_export_image(node_name=None, file_path=str(target), model_name=model_name)
        backend_result["file"] = str(target)
        backend_result["file_size"] = target.stat().st_size if target.exists() else 0
        backend_result["success"] = bool(backend_result.get("success")) and target.exists() and target.stat().st_size > 0
        return backend_result
    except Exception as exc:
        return {"success": False, "error": f"Failed to export plot image: {exc}", "file": str(target), "plot_group": plot_group}


def plot_export_geometry_view(
    file_path: Optional[str] = None,
    plot_group: str = "pg_geom_view",
    component_name: str = "comp1",
    geometry_name: str = "geom1",
    width: int = 1200,
    height: int = 900,
    model_name: Optional[str] = None,
) -> dict:
    """Create a geometry plot group if needed and export it to PNG."""
    if width <= 0 or height <= 0:
        return {"success": False, "error": "width and height must be positive."}
    model, error = current_model(model_name)
    if error:
        return error
    target = _default_plot_path(file_path, "geometry_view.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = model.java.result()
        existing = list_tags(result)
        if plot_group in existing:
            group = result(plot_group)
        else:
            group = result.create(plot_group, "PlotGroup3D")
            group.label("Geometry View")
        try:
            group.set("data", "none")
        except Exception:
            pass
        if "geom" not in list_tags(group.feature()):
            feature = group.feature().create("geom", "Geometry")
            set_properties(feature, {"geom": geometry_name, "component": component_name})
        export = _create_image_export(model, plot_group, target, width, height)
        return {
            "success": target.exists() and target.stat().st_size > 0,
            "file": str(target),
            "plot_group": plot_group,
            "geometry": geometry_name,
            "component": component_name,
            "export": export,
            "file_size": target.stat().st_size if target.exists() else 0,
        }
    except Exception as exc:
        return {"success": False, "error": f"Failed to export geometry view: {exc}", "file": str(target), "plot_group": plot_group}


def _create_image_export(model, plot_group: str, target: Path, width: int, height: int) -> dict:
    exports = model.java.result().export()
    tag = unique_tag(list_tags(exports), "img")
    export = exports.create(tag, "Image")
    prop_result = set_properties(
        export,
        {
            "plotgroup": plot_group,
            "pngfilename": str(target),
            "filename": str(target),
            "imagetype": "png",
            "width": str(width),
            "height": str(height),
        },
    )
    export.run()
    return {"tag": tag, "property_result": prop_result}


def _resolve_plot_group_tag(model, plot_group: Optional[str]) -> Optional[str]:
    try:
        result = model.java.result()
        tags = list_tags(result)
        if not tags:
            tags = [str(tag) for tag in result.tags()]
        if plot_group is None:
            return tags[0] if tags else None
        if plot_group in tags:
            return plot_group
        for tag in tags:
            try:
                node = result.get(tag)
            except Exception:
                try:
                    node = result(tag)
                except Exception:
                    continue
            label = str(safe_call(node, "label", ""))
            if plot_group == label:
                return tag
        return plot_group
    except Exception:
        return plot_group


def _default_plot_path(file_path: Optional[str], name: str) -> Path:
    if file_path:
        return Path(file_path)
    directory = MODELS_DIR / "exports"
    return directory / name
