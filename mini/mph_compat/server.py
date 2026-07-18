"""COMSOL Ampacity MCP server - 精简版
只包含核心: 启动/加载/参数/求解/读结果/寻优.
由桃井裁剪自原版, 去掉了 RAG/assistants/validators/workflows/gui_backend.
"""
from __future__ import annotations

from typing import Any, List, Optional, Sequence, Union

try:
    from mcp.server.fastmcp import FastMCP
    _HAS_MCP = True
except Exception:
    FastMCP = None  # type: ignore[assignment]
    _HAS_MCP = False

from . import audit
from .backends import mph_backend
from .state import get_default_backend, set_default_backend
from .tools import boundary as boundary_tools
from .tools import geometry as geometry_tools
from .tools import materials as material_tools
from .tools import mesh as mesh_tools
from .tools import physics as physics_tools
from .tools import plot as plot_tools
from .tools import results as results_tools
from .tools import selection as selection_tools
from .tools import study as study_tools
from .tools import templates as template_tools

mcp = FastMCP("comsol-ampacity-mcp") if _HAS_MCP else None


def mcp_tool(*args: Any, **kwargs: Any):
    """Register an MCP tool with in-memory call auditing."""
    def decorator(fn):
        return mcp.tool(*args, **kwargs)(audit.audit_tool(fn.__name__)(fn))
    return decorator


# ---------------------------------------------------------------------------
# Backend status
# ---------------------------------------------------------------------------

@mcp_tool()
def backend_status() -> dict:
    """Return availability and status for the mph backend."""
    return {
        "success": True,
        "default_backend": get_default_backend(),
        "mph_available": mph_backend.is_available(),
        "mph_status": mph_backend.mph_status(),
    }


@mcp_tool()
def backend_set_default(backend: str = "mph") -> dict:
    """Set default backend (only 'mph' supported in this build)."""
    return set_default_backend(backend)


@mcp_tool()
def mcp_call_stats() -> dict:
    """Return in-memory MCP tool call counts and success rates."""
    return audit.stats()


@mcp_tool()
def mcp_call_recent(limit: int = 20) -> dict:
    """Return recent MCP tool calls from this server process."""
    return audit.recent(limit=limit)


@mcp_tool()
def mcp_call_reset() -> dict:
    """Reset in-memory MCP tool call counters for a clean test run."""
    return audit.reset()


# ---------------------------------------------------------------------------
# mph session control
# ---------------------------------------------------------------------------

@mcp_tool()
def mph_start(cores: Optional[int] = None, version: Optional[str] = None) -> dict:
    """Start a local COMSOL mph session (blocking, ~10-30s)."""
    return mph_backend.mph_start(cores=cores, version=version)


@mcp_tool()
def mph_start_async(cores: Optional[int] = None, version: Optional[str] = None) -> dict:
    """Start mph session in a background task; poll with mph_start_status."""
    return mph_backend.mph_start_async(cores=cores, version=version)


@mcp_tool()
def mph_start_status(task_id: Optional[str] = None) -> dict:
    """Check status of an async mph_start task."""
    return mph_backend.mph_start_status(task_id=task_id)


@mcp_tool()
def mph_cancel_start(task_id: Optional[str] = None) -> dict:
    """Cancel a pending mph_start task."""
    return mph_backend.mph_cancel_start(task_id=task_id)


@mcp_tool()
def mph_connect(port: int, host: str = "localhost") -> dict:
    """Connect to a running COMSOL server on a given port."""
    return mph_backend.mph_connect(port=port, host=host)


@mcp_tool()
def mph_status() -> dict:
    """Return current mph session status (cores, version, models, etc)."""
    return mph_backend.mph_status()


@mcp_tool()
def mph_disconnect() -> dict:
    """Disconnect from the mph session. Free the Java VM."""
    return mph_backend.mph_disconnect()


# ---------------------------------------------------------------------------
# Model operations
# ---------------------------------------------------------------------------

@mcp_tool()
def model_create(name: Optional[str] = None) -> dict:
    """Create a new empty COMSOL model."""
    return mph_backend.model_create(name=name)


@mcp_tool()
def model_load(file_path: str) -> dict:
    """Load a .mph model file from disk and set it as current."""
    return mph_backend.model_load(file_path=file_path)


@mcp_tool()
def model_save(file_path: Optional[str] = None, model_name: Optional[str] = None) -> dict:
    """Save the current model to disk."""
    return mph_backend.model_save(file_path=file_path, model_name=model_name)


@mcp_tool()
def model_save_version(description: Optional[str] = None, model_name: Optional[str] = None) -> dict:
    """Save a versioned copy of the current model."""
    return mph_backend.model_save_version(description=description, model_name=model_name)


@mcp_tool()
def model_list() -> dict:
    """List all loaded models in the session."""
    return mph_backend.model_list()


@mcp_tool()
def model_inspect(model_name: Optional[str] = None) -> dict:
    """Return a high-level inspection of a model (parameters, studies, physics, materials, ...)."""
    return mph_backend.model_inspect(model_name=model_name)


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

@mcp_tool()
def param_set(name: str, value: str, description: Optional[str] = None, model_name: Optional[str] = None) -> dict:
    """Set a model parameter (e.g. param_set('I', '1054'))."""
    return mph_backend.param_set(name=name, value=value, description=description, model_name=model_name)


@mcp_tool()
def param_get(name: str, evaluate: bool = False, model_name: Optional[str] = None) -> dict:
    """Get a model parameter value (set evaluate=True for the evaluated numeric value)."""
    return mph_backend.param_get(name=name, evaluate=evaluate, model_name=model_name)


@mcp_tool()
def param_list(evaluate: bool = False, model_name: Optional[str] = None) -> dict:
    """List all model parameters."""
    return mph_backend.param_list(evaluate=evaluate, model_name=model_name)


@mcp_tool()
def param_remove(name: str, model_name: Optional[str] = None) -> dict:
    """Remove a model parameter."""
    return mph_backend.param_remove(name=name, model_name=model_name)


# ---------------------------------------------------------------------------
# Studies & solving
# ---------------------------------------------------------------------------

@mcp_tool()
def study_list(model_name: Optional[str] = None) -> dict:
    """List studies defined in the current model."""
    return study_tools.study_list(model_name=model_name)


@mcp_tool()
def study_create(model_name: Optional[str] = None, label: str = "Study") -> dict:
    """Create an empty study node."""
    return study_tools.study_create(model_name=model_name, label=label)


@mcp_tool()
def study_create_stationary(model_name: Optional[str] = None, label: str = "Stationary Study") -> dict:
    """Create a stationary study node (used for steady-state thermal, etc.)."""
    return study_tools.study_create_stationary(model_name=model_name, label=label)


@mcp_tool()
def study_create_time_dependent(model_name: Optional[str] = None, label: str = "Time Dependent") -> dict:
    """Create a time-dependent study node."""
    return study_tools.study_create_time_dependent(model_name=model_name, label=label)


@mcp_tool()
def study_create_frequency_domain(model_name: Optional[str] = None, label: str = "Frequency Domain") -> dict:
    """Create a frequency-domain study node."""
    return study_tools.study_create_frequency_domain(model_name=model_name, label=label)


@mcp_tool()
def study_solve(study_name: str = "研究 1", model_name: Optional[str] = None) -> dict:
    """Solve a study synchronously (blocks until done, ~30-300s)."""
    return study_tools.study_solve(study_name=study_name, model_name=model_name)


@mcp_tool()
def study_validate(model_name: Optional[str] = None) -> dict:
    """Validate the current study configuration (solver settings, etc.)."""
    return study_tools.study_validate(model_name=model_name)


@mcp_tool()
def solutions_list(model_name: Optional[str] = None) -> dict:
    """List all solutions available in the current model."""
    return study_tools.solutions_list(model_name=model_name)


@mcp_tool()
def solver_configure_stationary(study_name: str = "研究 1", mode: str = "segregated") -> dict:
    """Configure the stationary solver (segregated vs direct)."""
    return study_tools.solver_configure_stationary(study_name=study_name, mode=mode)


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

@mcp_tool()
def geometry_list(model_name: Optional[str] = None) -> dict:
    """List geometries in the current model."""
    return geometry_tools.geometry_list(model_name=model_name)


@mcp_tool()
def geometry_create(model_name: Optional[str] = None) -> dict:
    """Create an empty geometry sequence."""
    return geometry_tools.geometry_create(model_name=model_name)


@mcp_tool()
def geometry_add_block(width: float, depth: float, height: float,
                      x: float = 0.0, y: float = 0.0, z: float = 0.0,
                      model_name: Optional[str] = None) -> dict:
    """Add a block primitive to the geometry."""
    return geometry_tools.geometry_add_block(
        width=width, depth=depth, height=height, x=x, y=y, z=z, model_name=model_name)


@mcp_tool()
def geometry_add_cylinder(radius: float, height: float,
                         x: float = 0.0, y: float = 0.0, z: float = 0.0,
                         axis: str = "z", model_name: Optional[str] = None) -> dict:
    """Add a cylinder primitive."""
    return geometry_tools.geometry_add_cylinder(
        radius=radius, height=height, x=x, y=y, z=z, axis=axis, model_name=model_name)


@mcp_tool()
def geometry_add_sphere(radius: float, x: float = 0.0, y: float = 0.0, z: float = 0.0,
                       model_name: Optional[str] = None) -> dict:
    """Add a sphere primitive."""
    return geometry_tools.geometry_add_sphere(
        radius=radius, x=x, y=y, z=z, model_name=model_name)


@mcp_tool()
def geometry_add_rectangle(width: float, height: float,
                          x: float = 0.0, y: float = 0.0,
                          model_name: Optional[str] = None) -> dict:
    """Add a 2D rectangle primitive."""
    return geometry_tools.geometry_add_rectangle(
        width=width, height=height, x=x, y=y, model_name=model_name)


@mcp_tool()
def geometry_add_circle(radius: float, x: float = 0.0, y: float = 0.0,
                      model_name: Optional[str] = None) -> dict:
    """Add a 2D circle primitive."""
    return geometry_tools.geometry_add_circle(
        radius=radius, x=x, y=y, model_name=model_name)


@mcp_tool()
def geometry_build(model_name: Optional[str] = None) -> dict:
    """Build the geometry sequence (run all features)."""
    return geometry_tools.geometry_build(model_name=model_name)


@mcp_tool()
def geometry_list_features(model_name: Optional[str] = None) -> dict:
    """List features in the geometry sequence."""
    return geometry_tools.geometry_list_features(model_name=model_name)


@mcp_tool()
def geometry_get_entity_counts(model_name: Optional[str] = None) -> dict:
    """Return counts of domains/boundaries/edges/points in the geometry."""
    return geometry_tools.geometry_get_entity_counts(model_name=model_name)


# ---------------------------------------------------------------------------
# Selections
# ---------------------------------------------------------------------------

@mcp_tool()
def selection_list(model_name: Optional[str] = None) -> dict:
    """List defined selections in the current model."""
    return selection_tools.selection_list(model_name=model_name)


@mcp_tool()
def selection_create_explicit(entities: list, dim: int, label: str = "Selection",
                              model_name: Optional[str] = None) -> dict:
    """Create a selection by explicit entity list (domains, boundaries, edges, points)."""
    return selection_tools.selection_create_explicit(
        entities=entities, dim=dim, label=label, model_name=model_name)


@mcp_tool()
def selection_create_box(xmin: float, xmax: float, ymin: float, ymax: float,
                         zmin: float = 0.0, zmax: float = 0.0,
                         entity_type: str = "domain",
                         label: str = "Box", model_name: Optional[str] = None) -> dict:
    """Create a box selection."""
    return selection_tools.selection_create_box(
        xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax, zmin=zmin, zmax=zmax,
        entity_type=entity_type, label=label, model_name=model_name)


@mcp_tool()
def selection_create_cylinder(axis: str, radius: float, height: float,
                              x: float = 0.0, y: float = 0.0, z: float = 0.0,
                              entity_type: str = "domain",
                              label: str = "Cylinder", model_name: Optional[str] = None) -> dict:
    """Create a cylinder selection."""
    return selection_tools.selection_create_cylinder(
        axis=axis, radius=radius, height=height, x=x, y=y, z=z,
        entity_type=entity_type, label=label, model_name=model_name)


@mcp_tool()
def selection_inspect_entities(selection: str, model_name: Optional[str] = None) -> dict:
    """List the entities inside a selection."""
    return selection_tools.selection_inspect_entities(selection=selection, model_name=model_name)


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

@mcp_tool()
def material_list(model_name: Optional[str] = None) -> dict:
    """List all materials defined in the model."""
    return material_tools.material_list(model_name=model_name)


@mcp_tool()
def material_create_blank(label: str = "Material", model_name: Optional[str] = None) -> dict:
    """Create a blank material node."""
    return material_tools.material_create_blank(label=label, model_name=model_name)


@mcp_tool()
def material_create_common(material: str, label: Optional[str] = None,
                           model_name: Optional[str] = None) -> dict:
    """Add a common built-in material (e.g. 'Copper', 'Air', 'Water')."""
    return material_tools.material_create_common(material=material, label=label, model_name=model_name)


@mcp_tool()
def material_set_property(material: str, property_name: str, value: Union[str, float],
                          model_name: Optional[str] = None) -> dict:
    """Set a single property on a material (e.g. 'thermal_conductivity', 'electric_conductivity')."""
    return material_tools.material_set_property(
        material=material, property_name=property_name, value=value, model_name=model_name)


@mcp_tool()
def material_assign_domains(material: str, domains: list,
                            model_name: Optional[str] = None) -> dict:
    """Assign a material to a list of domain entities."""
    return material_tools.material_assign_domains(
        material=material, domains=domains, model_name=model_name)


@mcp_tool()
def material_info(material: str, model_name: Optional[str] = None) -> dict:
    """Inspect a material's properties."""
    return material_tools.material_info(material=material, model_name=model_name)


# ---------------------------------------------------------------------------
# Physics
# ---------------------------------------------------------------------------

@mcp_tool()
def physics_get_available_interfaces() -> dict:
    """List all physics interfaces that can be added."""
    return physics_tools.physics_get_available_interfaces()


@mcp_tool()
def physics_list(model_name: Optional[str] = None) -> dict:
    """List physics interfaces defined in the current model."""
    return physics_tools.physics_list(model_name=model_name)


@mcp_tool()
def physics_add(physics_type: str, label: Optional[str] = None,
                model_name: Optional[str] = None) -> dict:
    """Add a physics interface by type identifier (e.g. 'ht', 'ec', 'spf')."""
    return physics_tools.physics_add(physics_type=physics_type, label=label, model_name=model_name)


@mcp_tool()
def physics_add_electrostatics(model_name: Optional[str] = None) -> dict:
    """Add the Electrostatics (es) interface."""
    return physics_tools.physics_add_electrostatics(model_name=model_name)


@mcp_tool()
def physics_add_heat_transfer(model_name: Optional[str] = None) -> dict:
    """Add the Heat Transfer (ht) interface."""
    return physics_tools.physics_add_heat_transfer(model_name=model_name)


@mcp_tool()
def physics_add_laminar_flow(model_name: Optional[str] = None) -> dict:
    """Add the Laminar Flow (spf) interface."""
    return physics_tools.physics_add_laminar_flow(model_name=model_name)


@mcp_tool()
def physics_add_solid_mechanics(model_name: Optional[str] = None) -> dict:
    """Add the Solid Mechanics (solid) interface."""
    return physics_tools.physics_add_solid_mechanics(model_name=model_name)


@mcp_tool()
def physics_add_magnetic_fields(model_name: Optional[str] = None) -> dict:
    """Add the Magnetic Fields (mf) interface."""
    return physics_tools.physics_add_magnetic_fields(model_name=model_name)


@mcp_tool()
def physics_add_general_form_pde(model_name: Optional[str] = None) -> dict:
    """Add a General Form PDE interface."""
    return physics_tools.physics_add_general_form_pde(model_name=model_name)


@mcp_tool()
def physics_add_darcy_law(model_name: Optional[str] = None) -> dict:
    """Add the Darcy's Law (dl) interface."""
    return physics_tools.physics_add_darcy_law(model_name=model_name)


@mcp_tool()
def darcy_set_porous_medium_properties(node: str, porosity: float, permeability: float,
                                       model_name: Optional[str] = None) -> dict:
    """Configure porous-medium properties on a Darcy node."""
    return physics_tools.darcy_set_porous_medium_properties(
        node=node, porosity=porosity, permeability=permeability, model_name=model_name)


@mcp_tool()
def heat_transfer_add_heat_source(node: str, Q: Union[str, float],
                                  model_name: Optional[str] = None) -> dict:
    """Add a heat source Q to a heat transfer domain/boundary node."""
    return physics_tools.heat_transfer_add_heat_source(
        node=node, Q=Q, model_name=model_name)


@mcp_tool()
def multiphysics_list(model_name: Optional[str] = None) -> dict:
    """List multiphysics couplings in the model."""
    return physics_tools.multiphysics_list(model_name=model_name)


@mcp_tool()
def multiphysics_add(physics_a: str, physics_b: str, coupling_type: str = "default",
                     model_name: Optional[str] = None) -> dict:
    """Add a multiphysics coupling (e.g. electromagnetic_heating)."""
    return physics_tools.multiphysics_add(
        physics_a=physics_a, physics_b=physics_b, coupling_type=coupling_type, model_name=model_name)


@mcp_tool()
def multiphysics_add_electromagnetic_heating(model_name: Optional[str] = None) -> dict:
    """Add the Electromagnetic Heating multiphysics coupling."""
    return physics_tools.multiphysics_add_electromagnetic_heating(model_name=model_name)


@mcp_tool()
def physics_list_features(physics: str, model_name: Optional[str] = None) -> dict:
    """List features in a physics interface (nodes, conditions, etc.)."""
    return physics_tools.physics_list_features(physics=physics, model_name=model_name)


@mcp_tool()
def physics_feature_info(physics: str, feature: str, model_name: Optional[str] = None) -> dict:
    """Inspect a specific physics feature."""
    return physics_tools.physics_feature_info(physics=physics, feature=feature, model_name=model_name)


@mcp_tool()
def physics_remove(physics: str, model_name: Optional[str] = None) -> dict:
    """Remove a physics interface from the model."""
    return physics_tools.physics_remove(physics=physics, model_name=model_name)


# ---------------------------------------------------------------------------
# Boundary conditions
# ---------------------------------------------------------------------------

@mcp_tool()
def boundary_get_presets(physics: str, model_name: Optional[str] = None) -> dict:
    """List preset boundary-condition types available for a physics interface."""
    return boundary_tools.boundary_get_presets(physics=physics, model_name=model_name)


@mcp_tool()
def boundary_add_condition(physics: str, condition: str, selection: list,
                           **kwargs: Any) -> dict:
    """Add a boundary condition on a selection (boundaries/domains/edges)."""
    return boundary_tools.boundary_add_condition(
        physics=physics, condition=condition, selection=selection, **kwargs)


@mcp_tool()
def boundary_add_preset(physics: str, preset: str, selection: list,
                        model_name: Optional[str] = None, **kwargs: Any) -> dict:
    """Add a preset boundary condition on a selection."""
    return boundary_tools.boundary_add_preset(
        physics=physics, preset=preset, selection=selection,
        model_name=model_name, **kwargs)


@mcp_tool()
def boundary_list_conditions(physics: str, model_name: Optional[str] = None) -> dict:
    """List all boundary conditions on a physics interface."""
    return boundary_tools.boundary_list_conditions(physics=physics, model_name=model_name)


@mcp_tool()
def boundary_remove_condition(physics: str, condition: str,
                              model_name: Optional[str] = None) -> dict:
    """Remove a boundary condition."""
    return boundary_tools.boundary_remove_condition(
        physics=physics, condition=condition, model_name=model_name)


# ---------------------------------------------------------------------------
# Mesh
# ---------------------------------------------------------------------------

@mcp_tool()
def mesh_list(model_name: Optional[str] = None) -> dict:
    """List mesh sequences in the model."""
    return mesh_tools.mesh_list(model_name=model_name)


@mcp_tool()
def mesh_create(model_name: Optional[str] = None) -> dict:
    """Create an empty mesh sequence."""
    return mesh_tools.mesh_create(model_name=model_name)


@mcp_tool()
def mesh_add_size(max_element_size: Optional[float] = None,
                  min_element_size: Optional[float] = None,
                  model_name: Optional[str] = None) -> dict:
    """Add a Size node controlling global element size."""
    return mesh_tools.mesh_add_size(
        max_element_size=max_element_size, min_element_size=min_element_size, model_name=model_name)


@mcp_tool()
def mesh_add_free_tetrahedral(model_name: Optional[str] = None) -> dict:
    """Add a free tetrahedral meshing node."""
    return mesh_tools.mesh_add_free_tetrahedral(model_name=model_name)


@mcp_tool()
def mesh_add_free_triangular(model_name: Optional[str] = None) -> dict:
    """Add a free triangular meshing node (2D / surface)."""
    return mesh_tools.mesh_add_free_triangular(model_name=model_name)


@mcp_tool()
def mesh_build(model_name: Optional[str] = None) -> dict:
    """Build the mesh (run all features)."""
    return mesh_tools.mesh_build(model_name=model_name)


@mcp_tool()
def mesh_info(model_name: Optional[str] = None) -> dict:
    """Return mesh statistics (element/vertex counts, features)."""
    return mesh_tools.mesh_info(model_name=model_name)


# ---------------------------------------------------------------------------
# Results & post-processing
# ---------------------------------------------------------------------------

@mcp_tool()
def results_evaluate(expression: str, unit: Optional[str] = None,
                     dataset: Optional[str] = None) -> dict:
    """Evaluate a COMSOL expression on a dataset. Returns a scalar or array of values."""
    return results_tools.results_evaluate(expression=expression, unit=unit, dataset=dataset)


@mcp_tool()
def results_global_evaluate(expression: str, unit: Optional[str] = None,
                            dataset: Optional[str] = None) -> dict:
    """Evaluate a global expression (e.g. average or integral)."""
    return results_tools.results_global_evaluate(expression=expression, unit=unit, dataset=dataset)


@mcp_tool()
def results_list_valid_expressions(physics_type: str = "general") -> dict:
    """List valid COMSOL expressions for the current physics."""
    return results_tools.results_list_valid_expressions(physics_type=physics_type)


@mcp_tool()
def results_probe_expression(expression: str, unit: Optional[str] = None,
                             dataset: Optional[str] = None) -> dict:
    """Probe an expression at the probe point(s) defined in the model."""
    return results_tools.results_probe_expression(expression=expression, unit=unit, dataset=dataset)


@mcp_tool()
def results_create_max_operator(expression: str, label: str = "MaxOp") -> dict:
    """Create a maximum-value operator (e.g. for surface max temperature)."""
    return results_tools.results_create_max_operator(expression=expression, label=label)


@mcp_tool()
def results_create_average_operator(expression: str, label: str = "AvgOp") -> dict:
    """Create an average-value operator."""
    return results_tools.results_create_average_operator(expression=expression, label=label)


@mcp_tool()
def results_evaluate_on_selection(expression: str, operator_name: str, selection: str) -> dict:
    """Evaluate an expression on a selection using a coupling operator."""
    return results_tools.results_evaluate_on_selection(
        expression=expression, operator_name=operator_name, selection=selection)


@mcp_tool()
def results_plots_list(model_name: Optional[str] = None) -> dict:
    """List all plot nodes in the model."""
    return results_tools.results_plots_list(model_name=model_name)


@mcp_tool()
def results_export_image(node_name: Optional[str] = None, file_path: Optional[str] = None,
                        model_name: Optional[str] = None) -> dict:
    """Export a plot to an image file."""
    return results_tools.results_export_image(
        node_name=node_name, file_path=file_path, model_name=model_name)


@mcp_tool()
def results_validate_physics(physics_type: Optional[str] = None, evaluate: bool = False) -> dict:
    """Validate that the model has all physics needed for the given results evaluation."""
    return results_tools.results_validate_physics(physics_type=physics_type, evaluate=evaluate)


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

@mcp_tool()
def plot_list(model_name: Optional[str] = None) -> dict:
    """List all plot nodes."""
    return plot_tools.plot_list(model_name=model_name)


@mcp_tool()
def plot_export_image(plot: str, file_path: str, model_name: Optional[str] = None) -> dict:
    """Export a plot to an image file."""
    return plot_tools.plot_export_image(plot=plot, file_path=file_path, model_name=model_name)


@mcp_tool()
def plot_export_geometry_view(file_path: str, model_name: Optional[str] = None) -> dict:
    """Export a geometry preview to an image file."""
    return plot_tools.plot_export_geometry_view(file_path=file_path, model_name=model_name)


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

@mcp_tool()
def template_list_models() -> dict:
    """List available built-in model templates."""
    return template_tools.template_list_models()


@mcp_tool()
def template_build_model(template_name: str, model_name: Optional[str] = None,
                        save_version: bool = True) -> dict:
    """Build a model from a built-in template."""
    return template_tools.template_build_model(
        template_name=template_name, model_name=model_name, save_version=save_version)


# ---------------------------------------------------------------------------
# Ampacity / Newton root finder
# ---------------------------------------------------------------------------

@mcp_tool()
def compute_ampacity(
    target_T_celsius: float = 90.0,
    param_name: str = "I",
    I_low: float = 500.0,
    I_high: float = 1500.0,
    T_at_I_low: Optional[float] = None,
    T_at_I_high: Optional[float] = None,
    study_name: str = "研究 1",
    solution_tag: Optional[str] = None,
    dataset: Optional[str] = None,
    expression: str = "max(T2, 1)",
    tolerance_celsius: float = 0.05,
    max_iterations: int = 8,
) -> dict:
    """Find the cable ampacity (current in amperes) that produces a target
    maximum temperature. Uses a Secant/quasi-Newton root-finder with
    bisection fallback when the stationary solver fails on a step.

    Args:
        target_T_celsius: Target maximum surface temperature in °C.
        param_name: COMSOL parameter that drives the heat source (default 'I').
        I_low, I_high: Search bracket. Provide T_at_I_low / T_at_I_high to skip
            the initial two solves if you already have them.
        T_at_I_low, T_at_I_high: Optional known temperatures at the bracket.
        study_name: Stationary study to solve (default '研究 1').
        solution_tag: Optional solution tag override.
        dataset: Optional dataset override (default '{study_name}//解 1').
        expression: COMSOL expression to evaluate (default 'max(T2, 1)').
        tolerance_celsius: Stop when |T - target| < tolerance.
        max_iterations: Hard cap on iterations.

    Returns:
        dict with success, converged, target_T, final_I, final_T, iterations,
        history, solve_count.
    """
    return _compute_ampacity_impl(
        target_T_celsius=target_T_celsius,
        param_name=param_name,
        I_low=I_low, I_high=I_high,
        T_at_I_low=T_at_I_low, T_at_I_high=T_at_I_high,
        study_name=study_name,
        solution_tag=solution_tag,
        dataset=dataset,
        expression=expression,
        tolerance_celsius=tolerance_celsius,
        max_iterations=max_iterations,
    )


# ---------------------------------------------------------------------------
# compute_ampacity implementation
# ---------------------------------------------------------------------------

def _solve_study_by_tag(preferred_label: str) -> dict:
    """Solve the only study in the current model via the Java study object.
    Bypasses m.solve('研究 1') (label, not tag) and study_solve() which fails
    intermittently with '未知研究' on 6.4 engine."""
    try:
        sess = mph_backend.session
        model_name = getattr(sess, "current_model", None)
        if not model_name:
            return {"success": False, "error": "No current model"}
        m = sess.get_model(model_name)
        tags = list(m.java.study().tags())
        if not tags:
            return {"success": False, "error": "No study found in model"}
        tag = tags[0]
        m.java.study(tag).run()
        return {"success": True, "study": tag}
    except Exception as exc:
        return {"success": False, "error": str(exc)[:200]}


def _read_max_temp(solution_tag, dataset: str, expression: str) -> Optional[float]:
    """Read max temperature across mesh nodes via m.evaluate.
    Returns None on failure. Handles numpy.ndarray, K->°C conversion."""
    try:
        import numpy as _np
        sess = mph_backend.session
        model_name = getattr(sess, "current_model", None)
        m = sess.get_model(model_name) if model_name else None
        if m is None:
            return None
        result = m.evaluate(expression, dataset=dataset)
        if isinstance(result, (int, float)):
            return float(result)
        if isinstance(result, _np.ndarray):
            arr = result.flatten()
            if arr.size == 0:
                return None
            vmax = float(arr.max())
            if vmax > 200.0:
                vmax -= 273.15
            return vmax
        if isinstance(result, list):
            flat = []
            for item in result:
                if isinstance(item, (int, float)):
                    flat.append(float(item))
                elif isinstance(item, (list, tuple)) and item:
                    if isinstance(item[0], (int, float)):
                        flat.append(float(item[0]))
            return max(flat) if flat else None
        return None
    except Exception:
        return None


def _compute_ampacity_impl(
    target_T_celsius, param_name, I_low, I_high,
    T_at_I_low, T_at_I_high,
    study_name, solution_tag, dataset,
    expression, tolerance_celsius, max_iterations,
) -> dict:
    if dataset is None:
        dataset = f"{study_name}//解 1"

    history: List[dict] = []
    solve_count = 0
    have_seeds = (T_at_I_low is not None) and (T_at_I_high is not None)

    def _step(I: float, ramp: bool = True):
        if ramp and not have_seeds and solve_count == 0 and abs(I) > 50:
            try:
                cur = mph_backend.param_get(param_name, evaluate=True)
                cur_val = float(cur.get("value", "0")) if isinstance(cur.get("value"), str) else float(cur.get("value", 0))
            except Exception:
                cur_val = None
            if cur_val and cur_val > 0:
                a = cur_val
                steps = []
                while abs(a - I) > 20:
                    a = a + (I - a) * 0.5
                    steps.append(int(a))
                steps.append(int(I))
                for s in steps:
                    mph_backend.param_set(param_name, str(s))
                    rr0 = _solve_study_by_tag(study_name)
                    if not rr0.get("success"):
                        return f"ramp-step {s}: {rr0.get('error')[:120]}"
                mph_backend.param_set(param_name, str(int(I)))
                rr1 = _solve_study_by_tag(study_name)
                if not rr1.get("success"):
                    return f"final {int(I)}: {rr1.get('error')[:120]}"
                return _read_max_temp(solution_tag, dataset, expression)
            else:
                mid = I * 0.5
                mph_backend.param_set(param_name, str(int(mid)))
                rr0 = _solve_study_by_tag(study_name)
                if not rr0.get("success"):
                    return f"ramp-mid {int(mid)}: {rr0.get('error')}"
        mph_backend.param_set(param_name, str(int(I)))
        rr = _solve_study_by_tag(study_name)
        if not rr.get("success"):
            return f"I={int(I)}: {rr.get('error')}"
        return _read_max_temp(solution_tag, dataset, expression)

    if T_at_I_low is None:
        T_at_I_low = _step(I_low, ramp=True)
        if T_at_I_low is None or isinstance(T_at_I_low, str):
            return {"success": False, "error": f"Initial solve at I={I_low} failed: {T_at_I_low}", "stage": "low"}
        solve_count += 1
    if T_at_I_high is None:
        T_at_I_high = _step(I_high, ramp=False)
        if T_at_I_high is None or isinstance(T_at_I_high, str):
            return {"success": False, "error": f"Initial solve at I={I_high} failed: {T_at_I_high}", "stage": "high"}
        solve_count += 1

    history.append({"iter": 0, "I": I_low, "T": T_at_I_low, "method": "bracket"})
    history.append({"iter": 1, "I": I_high, "T": T_at_I_high, "method": "bracket"})

    if not (min(T_at_I_low, T_at_I_high) <= target_T_celsius <= max(T_at_I_low, T_at_I_high)):
        return {
            "success": False,
            "error": f"Target {target_T_celsius}°C not within bracket "
                     f"[{min(T_at_I_low, T_at_I_high):.2f}, {max(T_at_I_low, T_at_I_high):.2f}]°C",
            "history": history,
        }

    I0, T0 = I_low, T_at_I_low
    I1, T1 = I_high, T_at_I_high
    converged = False
    final_I, final_T = I1, T1

    for n in range(2, max_iterations + 1):
        dTdI = (T1 - T0) / (I1 - I0) if I1 != I0 else 1.0
        I_new = I1 - (T1 - target_T_celsius) / dTdI
        I_new = max(I_low, min(I_high, int(round(I_new))))

        T_new = _step(I_new, ramp=False)
        if T_new is None or isinstance(T_new, str):
            I_new = int((I0 + I1) // 2)
            T_new = _step(I_new, ramp=False)
            if T_new is None or isinstance(T_new, str):
                history.append({"iter": n, "I": I_new, "T": None, "method": "bisection-fail"})
                break
            method = "bisection"
        else:
            method = "secant"
        solve_count += 1
        dT = T_new - target_T_celsius
        history.append({"iter": n, "I": I_new, "T": T_new, "dT": dT, "method": method})
        final_I, final_T = I_new, T_new

        if abs(dT) < tolerance_celsius:
            converged = True
            break
        if T_new < target_T_celsius:
            I0, T0 = I_new, T_new
        else:
            I1, T1 = I_new, T_new

    return {
        "success": True,
        "converged": converged,
        "target_T": target_T_celsius,
        "final_I": final_I,
        "final_T": final_T,
        "iterations": len(history) - 2,
        "solve_count": solve_count,
        "tolerance_celsius": tolerance_celsius,
        "expression": expression,
        "history": history,
    }


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()