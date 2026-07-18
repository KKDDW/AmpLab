"""Canonical model-building templates for simple COMSOL examples."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from ..backends import mph_backend
from ..config import PROJECT_ROOT
# 主人: 桃井注释掉 RAG 引用, 这个 MCP 不需要知识库.
# from ..knowledge import retriever


# Stub: 提供一个空的 retriever 接口, 保持 templates.py 可用
class _RetrieverStub:
    @staticmethod
    def rag_search(query, module=None, n_results=5):
        return {"success": False, "skipped": True, "reason": "RAG disabled in this build"}


retriever = _RetrieverStub()
from . import boundary, geometry, materials, mesh, physics, plot, results, study


TEMPLATE_CATALOG = {
    "electrostatic_disk_capacitor": {
        "physics_type": "electrostatics",
        "description": "2D axisymmetric-style disk capacitor starter model using electrostatics.",
        "parameters": {"R_disk": "2[mm]", "t_diel": "0.5[mm]", "V0": "1[V]", "eps_r": "3.9"},
    },
    "steady_heat_block": {
        "physics_type": "heat_transfer",
        "description": "3D block with fixed-temperature and heat-flux boundary placeholders.",
        "parameters": {"L": "10[mm]", "W": "5[mm]", "H": "2[mm]", "T_hot": "350[K]", "T_cold": "293.15[K]"},
    },
    "laminar_channel": {
        "physics_type": "fluid_flow",
        "description": "3D rectangular channel with laminar-flow placeholders.",
        "parameters": {"L": "50[mm]", "W": "5[mm]", "H": "1[mm]", "U0": "0.01[m/s]", "p0": "0[Pa]"},
    },
    "fixed_beam": {
        "physics_type": "solid_mechanics",
        "description": "3D cantilever beam starter model with fixed and load boundary placeholders.",
        "parameters": {"L": "50[mm]", "W": "5[mm]", "H": "2[mm]", "load0": "1e5[Pa]"},
    },
    "square_spiral_inductor_air_dc": {
        "physics_type": "magnetic_fields",
        "description": "3D copper square spiral inductor in air with a DC coil current excitation.",
        "parameters": {
            "N_turns": "3",
            "trace_w": "0.2[mm]",
            "gap": "0.15[mm]",
            "trace_t": "35[um]",
            "outer_size": "5[mm]",
            "I0": "1[A]",
            "J0": "I0/(trace_w*trace_t)",
            "air_margin": "3[mm]",
        },
        "output_dir": "results/square_spiral_inductor_air_dc",
    },
}


def template_list_models() -> dict:
    """List canonical auto-build templates."""
    return {"success": True, "templates": TEMPLATE_CATALOG, "count": len(TEMPLATE_CATALOG)}


def template_build_model(template_name: str, model_name: Optional[str] = None, save_version: bool = True) -> dict:
    """Build a conservative starter model for a supported canonical template."""
    if template_name not in TEMPLATE_CATALOG:
        return {"success": False, "error": f"Unknown template: {template_name}", "available": sorted(TEMPLATE_CATALOG)}
    if mph_backend.session.client is None:
        return {"success": False, "error": "No active mph session. Start with mph_start first."}
    if template_name == "electrostatic_disk_capacitor":
        return _build_electrostatic_disk(model_name=model_name, save_version=save_version)
    if template_name == "steady_heat_block":
        return _build_heat_block(model_name=model_name, save_version=save_version)
    if template_name == "laminar_channel":
        return _build_laminar_channel(model_name=model_name, save_version=save_version)
    if template_name == "fixed_beam":
        return _build_fixed_beam(model_name=model_name, save_version=save_version)
    if template_name == "square_spiral_inductor_air_dc":
        return _build_square_spiral_inductor_air_dc(model_name=model_name, save_version=save_version)
    return {"success": False, "error": f"Template is registered but not implemented: {template_name}"}


def _build_electrostatic_disk(model_name: Optional[str], save_version: bool) -> dict:
    created = mph_backend.model_create(model_name or "electrostatic_disk_capacitor")
    steps = {"model_create": created}
    if not created.get("success"):
        return _template_response(False, "electrostatic_disk_capacitor", steps)
    _set_params(TEMPLATE_CATALOG["electrostatic_disk_capacitor"]["parameters"], steps)
    steps["component"] = geometry.model_create_component()
    steps["geometry_create"] = geometry.geometry_create(space_dimension=2)
    steps["dielectric"] = geometry.geometry_add_rectangle(position=("0", "0"), size=("R_disk", "t_diel"), feature_name="diel")
    steps["geometry_build"] = geometry.geometry_build()
    steps["material"] = materials.material_create_blank("Dielectric", tag="mat_diel")
    steps["material_props"] = materials.material_set_property("mat_diel", properties={"relpermittivity": "eps_r"})
    steps["physics"] = physics.physics_add_electrostatics()
    steps["ground"] = boundary.boundary_add_preset("electrostatics_ground", boundaries=[2], feature_tag="gnd1")
    steps["terminal"] = boundary.boundary_add_preset("electrostatics_terminal", boundaries=[3], properties={"V0": "V0"}, feature_tag="term1")
    steps["mesh"] = mesh.mesh_create()
    steps["mesh_size"] = mesh.mesh_add_size(size="finer")
    steps["mesh_tri"] = mesh.mesh_add_free_triangular()
    steps["study"] = study.study_create_stationary(physics_tags=["es"])
    steps["save_version"] = mph_backend.model_save_version("template electrostatic disk capacitor") if save_version else {"success": True, "skipped": True}
    return _template_response(_all_required_success(steps, ["model_create", "geometry_build", "physics", "mesh", "study", "save_version"]), "electrostatic_disk_capacitor", steps)


def _build_heat_block(model_name: Optional[str], save_version: bool) -> dict:
    created = mph_backend.model_create(model_name or "steady_heat_block")
    steps = {"model_create": created}
    if not created.get("success"):
        return _template_response(False, "steady_heat_block", steps)
    _set_params(TEMPLATE_CATALOG["steady_heat_block"]["parameters"], steps)
    steps["component"] = geometry.model_create_component()
    steps["geometry_create"] = geometry.geometry_create(space_dimension=3)
    steps["block"] = geometry.geometry_add_block(size=("L", "W", "H"), feature_name="blk1")
    steps["geometry_build"] = geometry.geometry_build()
    steps["material"] = materials.material_create_common("silicon", domains=[1])
    steps["physics"] = physics.physics_add_heat_transfer()
    steps["cold"] = boundary.boundary_add_preset("heat_temperature", boundaries=[1], properties={"T0": "T_cold"}, feature_tag="tcold")
    steps["hot"] = boundary.boundary_add_preset("heat_temperature", boundaries=[2], properties={"T0": "T_hot"}, feature_tag="thot")
    steps["mesh"] = mesh.mesh_create()
    steps["mesh_tet"] = mesh.mesh_add_free_tetrahedral()
    steps["study"] = study.study_create_stationary(physics_tags=["ht"])
    steps["save_version"] = mph_backend.model_save_version("template steady heat block") if save_version else {"success": True, "skipped": True}
    return _template_response(_all_required_success(steps, ["model_create", "geometry_build", "physics", "mesh", "study", "save_version"]), "steady_heat_block", steps)


def _build_laminar_channel(model_name: Optional[str], save_version: bool) -> dict:
    created = mph_backend.model_create(model_name or "laminar_channel")
    steps = {"model_create": created}
    if not created.get("success"):
        return _template_response(False, "laminar_channel", steps)
    _set_params(TEMPLATE_CATALOG["laminar_channel"]["parameters"], steps)
    steps["component"] = geometry.model_create_component()
    steps["geometry_create"] = geometry.geometry_create(space_dimension=3)
    steps["channel"] = geometry.geometry_add_block(size=("L", "W", "H"), feature_name="chan1")
    steps["geometry_build"] = geometry.geometry_build()
    steps["material"] = materials.material_create_common("water", domains=[1])
    steps["physics"] = physics.physics_add_laminar_flow()
    steps["inlet"] = boundary.boundary_add_preset("flow_inlet", boundaries=[1], properties={"U0": "U0"}, feature_tag="inl1")
    steps["outlet"] = boundary.boundary_add_preset("flow_outlet", boundaries=[2], properties={"p0": "p0"}, feature_tag="out1")
    steps["mesh"] = mesh.mesh_create()
    steps["mesh_tet"] = mesh.mesh_add_free_tetrahedral()
    steps["study"] = study.study_create_stationary(physics_tags=["spf"])
    steps["save_version"] = mph_backend.model_save_version("template laminar channel") if save_version else {"success": True, "skipped": True}
    return _template_response(_all_required_success(steps, ["model_create", "geometry_build", "physics", "mesh", "study", "save_version"]), "laminar_channel", steps)


def _build_fixed_beam(model_name: Optional[str], save_version: bool) -> dict:
    created = mph_backend.model_create(model_name or "fixed_beam")
    steps = {"model_create": created}
    if not created.get("success"):
        return _template_response(False, "fixed_beam", steps)
    _set_params(TEMPLATE_CATALOG["fixed_beam"]["parameters"], steps)
    steps["component"] = geometry.model_create_component()
    steps["geometry_create"] = geometry.geometry_create(space_dimension=3)
    steps["beam"] = geometry.geometry_add_block(size=("L", "W", "H"), feature_name="beam1")
    steps["geometry_build"] = geometry.geometry_build()
    steps["material"] = materials.material_create_common("aluminum", domains=[1])
    steps["physics"] = physics.physics_add_solid_mechanics()
    steps["fixed"] = boundary.boundary_add_preset("solid_fixed", boundaries=[1], feature_tag="fix1")
    steps["load"] = boundary.boundary_add_preset("solid_boundary_load", boundaries=[2], properties={"FperArea": "load0"}, feature_tag="load1")
    steps["mesh"] = mesh.mesh_create()
    steps["mesh_tet"] = mesh.mesh_add_free_tetrahedral()
    steps["study"] = study.study_create_stationary(physics_tags=["solid"])
    steps["save_version"] = mph_backend.model_save_version("template fixed beam") if save_version else {"success": True, "skipped": True}
    return _template_response(_all_required_success(steps, ["model_create", "geometry_build", "physics", "mesh", "study", "save_version"]), "fixed_beam", steps)


def _build_square_spiral_inductor_air_dc(model_name: Optional[str], save_version: bool) -> dict:
    template_name = "square_spiral_inductor_air_dc"
    output_dir = PROJECT_ROOT / "results" / template_name
    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / f"{template_name}.mph"
    report_path = output_dir / "build_report.json"
    geometry_png = output_dir / "geometry_view.png"
    magnetic_png = output_dir / "magnetic_field.png"

    steps: dict[str, Any] = {
        "output_dir": str(output_dir),
        "model_path": str(model_path),
        "parameters": TEMPLATE_CATALOG[template_name]["parameters"],
    }
    created = mph_backend.model_create(model_name or template_name)
    steps["model_create"] = created
    if not created.get("success"):
        return _write_template_report(False, template_name, steps, report_path)

    _set_params(TEMPLATE_CATALOG[template_name]["parameters"], steps)
    _set_numeric_helper_params(steps)
    steps["component"] = geometry.model_create_component()
    steps["geometry"] = _build_square_spiral_geometry(steps)
    steps["geometry_build"] = geometry.geometry_build()
    steps["materials"] = _create_inductor_materials(steps)
    steps["physics"] = _create_magnetic_fields_current_density_physics(steps)
    steps["mesh"] = _create_inductor_mesh()
    steps["study"] = _create_inductor_study()
    steps["solve"] = study.study_solve()
    steps["expressions"] = {
        "registry": results.results_list_valid_expressions("magnetic_fields"),
        "mf.normB": results.results_probe_expression("mf.normB"),
        "mf.intWm": results.results_probe_expression("mf.intWm"),
        "2*mf.intWm/I0^2": results.results_probe_expression("2*mf.intWm/I0^2"),
    }
    steps["plots"] = {
        "geometry": plot.plot_export_geometry_view(file_path=str(geometry_png), width=1000, height=800),
        "magnetic": plot.plot_export_image(file_path=str(magnetic_png), width=1000, height=800),
    }
    steps["inspect"] = mph_backend.model_inspect()
    steps["rag"] = retriever.rag_search("magnetic fields coil current inductance magnetic energy", module="ACDC_Module")
    steps["save_model"] = mph_backend.model_save(str(model_path))
    if save_version:
        steps["save_version"] = mph_backend.model_save_version("square spiral inductor air dc")
    else:
        steps["save_version"] = {"success": True, "skipped": True}

    success = bool(steps["save_model"].get("success")) and bool(steps["geometry_build"].get("success"))
    return _write_template_report(success, template_name, steps, report_path)


def _set_params(parameters: dict[str, str], steps: dict) -> None:
    for name, value in parameters.items():
        steps[f"param_{name}"] = mph_backend.param_set(name, value)


def _set_numeric_helper_params(steps: dict) -> None:
    helper_params = {
        "outer_size_m": "outer_size/1[m]",
        "trace_w_m": "trace_w/1[m]",
        "gap_m": "gap/1[m]",
        "trace_t_m": "trace_t/1[m]",
        "air_margin_m": "air_margin/1[m]",
    }
    for name, value in helper_params.items():
        steps[f"param_{name}"] = mph_backend.param_set(name, value)


def _build_square_spiral_geometry(steps: dict) -> dict:
    model = mph_backend.session.get_model()
    if model is None:
        return {"success": False, "error": "No current model."}
    try:
        comp = model.java.component("comp1")
    except Exception:
        comp = model.java.component().create("comp1", True)
    try:
        geom = comp.geom("geom1")
    except Exception:
        geom = comp.geom().create("geom1", 3)
    geom.lengthUnit("mm")
    created_features: list[str] = []
    segment_tags = []
    for segment in _square_spiral_segments():
        feature = geom.feature().create(segment["tag"], "Block")
        feature.set("pos", segment["pos"])
        feature.set("size", segment["size"])
        feature.set("selresult", "on")
        feature.set("selresultshow", "dom")
        segment_tags.append(segment["tag"])
        created_features.append(segment["tag"])
    air = geom.feature().create("airbox", "Block")
    air.set("pos", ["-outer_size_m/2-air_margin_m", "-outer_size_m/2-air_margin_m", "-air_margin_m"])
    air.set("size", ["outer_size_m+2*air_margin_m", "outer_size_m+2*air_margin_m", "2*air_margin_m+trace_t_m"])
    air.set("selresult", "on")
    air.set("selresultshow", "dom")
    created_features.append("airbox")
    union = geom.feature().create("coil_union", "Union")
    union.selection("input").set(segment_tags)
    union.set("intbnd", "off")
    union.set("selresult", "on")
    union.set("selresultshow", "dom")
    created_features.append("coil_union")
    _create_coil_terminal_selections(comp)
    try:
        geom.run()
    except Exception as exc:
        return {"success": False, "error": f"Failed to run inductor geometry: {exc}", "features": created_features}
    return {
        "success": True,
        "features": created_features,
        "coil_segments": segment_tags,
        "coil_selection": "geom1_coil_union_dom",
        "air_selection": "geom1_airbox_dom",
        "input_selection": "sel_coil_input",
        "output_selection": "sel_coil_output",
    }


def _square_spiral_segments() -> list[dict[str, Any]]:
    # Numeric helper parameters are dimensionless SI-meter expressions.
    return [
        {"tag": "seg1_top", "pos": ["-outer_size_m/2", "outer_size_m/2-trace_w_m", "0"], "size": ["outer_size_m", "trace_w_m", "trace_t_m"], "Je": ["J0", "0", "0"]},
        {"tag": "seg1_right", "pos": ["outer_size_m/2-trace_w_m", "-outer_size_m/2+trace_w_m+gap_m", "0"], "size": ["trace_w_m", "outer_size_m-2*trace_w_m-gap_m", "trace_t_m"], "Je": ["0", "-J0", "0"]},
        {"tag": "seg1_bottom", "pos": ["-outer_size_m/2+trace_w_m+gap_m", "-outer_size_m/2+trace_w_m+gap_m", "0"], "size": ["outer_size_m-trace_w_m-gap_m", "trace_w_m", "trace_t_m"], "Je": ["-J0", "0", "0"]},
        {"tag": "seg1_left", "pos": ["-outer_size_m/2+trace_w_m+gap_m", "-outer_size_m/2+trace_w_m+gap_m", "0"], "size": ["trace_w_m", "outer_size_m-2*(trace_w_m+gap_m)", "trace_t_m"], "Je": ["0", "J0", "0"]},
        {"tag": "seg2_top", "pos": ["-outer_size_m/2+trace_w_m+gap_m", "outer_size_m/2-2*trace_w_m-gap_m", "0"], "size": ["outer_size_m-2*(trace_w_m+gap_m)", "trace_w_m", "trace_t_m"], "Je": ["J0", "0", "0"]},
        {"tag": "seg2_right", "pos": ["outer_size_m/2-2*trace_w_m-gap_m", "-outer_size_m/2+2*(trace_w_m+gap_m)", "0"], "size": ["trace_w_m", "outer_size_m-4*(trace_w_m+gap_m)+gap_m", "trace_t_m"], "Je": ["0", "-J0", "0"]},
        {"tag": "seg2_bottom", "pos": ["-outer_size_m/2+2*(trace_w_m+gap_m)", "-outer_size_m/2+2*(trace_w_m+gap_m)", "0"], "size": ["outer_size_m-3*trace_w_m-3*gap_m", "trace_w_m", "trace_t_m"], "Je": ["-J0", "0", "0"]},
        {"tag": "seg2_left", "pos": ["-outer_size_m/2+2*(trace_w_m+gap_m)", "-outer_size_m/2+2*(trace_w_m+gap_m)", "0"], "size": ["trace_w_m", "outer_size_m-4*(trace_w_m+gap_m)", "trace_t_m"], "Je": ["0", "J0", "0"]},
        {"tag": "seg3_top", "pos": ["-outer_size_m/2+2*(trace_w_m+gap_m)", "outer_size_m/2-3*trace_w_m-2*gap_m", "0"], "size": ["outer_size_m-4*(trace_w_m+gap_m)", "trace_w_m", "trace_t_m"], "Je": ["J0", "0", "0"]},
        {"tag": "seg3_right", "pos": ["outer_size_m/2-3*trace_w_m-2*gap_m", "-outer_size_m/2+3*(trace_w_m+gap_m)", "0"], "size": ["trace_w_m", "outer_size_m-6*(trace_w_m+gap_m)+gap_m", "trace_t_m"], "Je": ["0", "-J0", "0"]},
    ]


def _create_inductor_materials(steps: dict) -> dict:
    model = mph_backend.session.get_model()
    if model is None:
        return {"success": False, "error": "No current model."}
    output: dict[str, Any] = {}
    output["air"] = materials.material_create_common("air", tag="mat_air")
    output["copper"] = materials.material_create_common("copper", tag="mat_cu")
    output["air_magnetic"] = materials.material_set_property("mat_air", properties={"mur": "1"})
    output["copper_magnetic"] = materials.material_set_property("mat_cu", properties={"mur": "1"})
    try:
        comp = model.java.component("comp1")
        comp.material("mat_air").selection().named("geom1_airbox_dom")
        comp.material("mat_cu").selection().named("geom1_coil_union_dom")
        output["assign_named"] = {"success": True, "air": "geom1_airbox_dom", "copper": "geom1_coil_union_dom"}
    except Exception as exc:
        output["assign_named"] = {"success": False, "error": str(exc)}
    output["success"] = (
        bool(output["air"].get("success"))
        and bool(output["copper"].get("success"))
        and bool(output["air_magnetic"].get("success"))
        and bool(output["copper_magnetic"].get("success"))
        and bool(output["assign_named"].get("success"))
    )
    return output


def _create_magnetic_fields_physics(steps: dict) -> dict:
    model = mph_backend.session.get_model()
    if model is None:
        return {"success": False, "error": "No current model."}
    output: dict[str, Any] = {}
    output["physics"] = physics.physics_add_magnetic_fields()
    try:
        comp = model.java.component("comp1")
        mf = comp.physics("mf")
        coil = mf.feature().create("coil1", "Coil", 3)
        coil.selection().named("geom1_coil_union_dom")
        coil.set("CoilExcitation", "Current")
        coil.set("ICoil", "I0")
        coil.set("N", "N_turns")
        coil.set("CoilType", "UserDefined")
        child_results = {}
        child_results["input"] = _safe_java_action(lambda: coil.feature("cg1").feature("ci1").selection().named("sel_coil_input"))
        child_results["output"] = _safe_java_action(lambda: coil.feature("cg1").feature("co1").selection().named("sel_coil_output"))
        child_results["terminal"] = _safe_java_action(lambda: coil.feature("ccc1").feature("ct1").selection().named("sel_coil_input"))
        output["coil"] = {
            "success": all(result.get("success") for result in child_results.values()),
            "tag": "coil1",
            "selection": "geom1_coil_union_dom",
            "ICoil": "I0",
            "N": "N_turns",
            "CoilType": "UserDefined",
            "terminal_selections": child_results,
        }
    except Exception as exc:
        output["coil"] = {"success": False, "error": str(exc)}
    output["success"] = bool(output["physics"].get("success")) and bool(output["coil"].get("success"))
    return output


def _create_magnetic_fields_current_density_physics(steps: dict) -> dict:
    model = mph_backend.session.get_model()
    if model is None:
        return {"success": False, "error": "No current model."}
    output: dict[str, Any] = {}
    output["physics"] = physics.physics_add_magnetic_fields()
    currents = []
    try:
        comp = model.java.component("comp1")
        mf = comp.physics("mf")
        for index, segment in enumerate(_square_spiral_segments(), start=1):
            tag = f"ecd{index}"
            feature = mf.feature().create(tag, "ExternalCurrentDensity", 3)
            feature.selection().named(f"geom1_{segment['tag']}_dom")
            feature.set("Je", segment["Je"])
            currents.append({"tag": tag, "segment": segment["tag"], "selection": f"geom1_{segment['tag']}_dom", "Je": segment["Je"], "success": True})
        output["external_current_density"] = {"success": True, "features": currents}
    except Exception as exc:
        output["external_current_density"] = {"success": False, "features": currents, "error": str(exc)}
    output["coil_diagnostic"] = _create_optional_coil_diagnostic()
    output["success"] = bool(output["physics"].get("success")) and bool(output["external_current_density"].get("success"))
    return output


def _create_optional_coil_diagnostic() -> dict:
    model = mph_backend.session.get_model()
    if model is None:
        return {"success": False, "error": "No current model."}
    try:
        comp = model.java.component("comp1")
        mf = comp.physics("mf")
        coil = mf.feature().create("coil_diag", "Coil", 3)
        coil.selection().named("geom1_coil_union_dom")
        coil.set("CoilExcitation", "Current")
        coil.set("ICoil", "I0")
        coil.set("N", "N_turns")
        coil.set("CoilType", "UserDefined")
        coil.active(False)
        return {"success": True, "tag": "coil_diag", "active": False, "note": "Diagnostic inactive coil node; ExternalCurrentDensity is used for robust DC solve."}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _create_coil_terminal_selections(comp) -> None:
    input_sel = comp.selection().create("sel_coil_input", "Box")
    input_sel.geom("geom1", 2)
    input_sel.set("xmin", "-outer_size_m/2-1e-9")
    input_sel.set("xmax", "-outer_size_m/2+1e-9")
    input_sel.set("ymin", "outer_size_m/2-trace_w_m-1e-9")
    input_sel.set("ymax", "outer_size_m/2+1e-9")
    input_sel.set("zmin", "-1e-9")
    input_sel.set("zmax", "trace_t_m+1e-9")
    output_sel = comp.selection().create("sel_coil_output", "Box")
    output_sel.geom("geom1", 2)
    output_sel.set("xmin", "outer_size_m/2-3*trace_w_m-2*gap_m-1e-9")
    output_sel.set("xmax", "outer_size_m/2-2*trace_w_m-2*gap_m+1e-9")
    output_sel.set("ymin", "-outer_size_m/2+3*(trace_w_m+gap_m)-1e-9")
    output_sel.set("ymax", "-outer_size_m/2+3*(trace_w_m+gap_m)+1e-9")
    output_sel.set("zmin", "-1e-9")
    output_sel.set("zmax", "trace_t_m+1e-9")


def _create_inductor_study() -> dict:
    model = mph_backend.session.get_model()
    if model is None:
        return {"success": False, "error": "No current model."}
    try:
        study_node = model.java.study().create("std1")
        step = study_node.feature().create("stat1", "Stationary")
        property_results = {}
        return {
            "success": True,
            "study": "std1",
            "step": {
                "tag": "stat1",
                "type": "Stationary",
                "label": str(step.label()),
                "property_results": property_results,
            },
        }
    except Exception as exc:
        return {"success": False, "error": f"Failed to create inductor study: {exc}"}


def _create_inductor_mesh() -> dict:
    output: dict[str, Any] = {}
    output["mesh"] = mesh.mesh_create()
    output["size"] = mesh.mesh_add_size(size="normal")
    output["tet"] = mesh.mesh_add_free_tetrahedral()
    output["build"] = mesh.mesh_build()
    output["success"] = bool(output["mesh"].get("success")) and bool(output["tet"].get("success"))
    return output


def _safe_java_action(fn) -> dict:
    try:
        value = fn()
        return {"success": True, "value": str(value)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _write_template_report(success: bool, template_name: str, steps: dict, report_path: Path) -> dict:
    failed = {key: value for key, value in steps.items() if isinstance(value, dict) and value.get("success") is False}
    response = {
        "success": success,
        "template": template_name,
        "steps": steps,
        "failed_steps": failed,
        "report_path": str(report_path),
        "note": "Square spiral inductor starter model. Verify coil domain orientation and magnetic boundary assumptions before using quantitative inductance.",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(response, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return response


def _all_required_success(steps: dict, required: list[str]) -> bool:
    return all(bool(steps.get(key, {}).get("success")) for key in required)


def _template_response(success: bool, template_name: str, steps: dict) -> dict:
    failed = {key: value for key, value in steps.items() if isinstance(value, dict) and value.get("success") is False}
    return {
        "success": success,
        "template": template_name,
        "steps": steps,
        "failed_steps": failed,
        "note": "This is a conservative starter model. Verify entity selections and physical assumptions before relying on quantitative results.",
    }
