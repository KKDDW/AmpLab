"""Result expression registry and derived value helpers."""

from __future__ import annotations

from typing import Optional, Sequence

from ..backends import mph_backend
from .common import current_model, list_tags, set_selection, unique_tag


EXPRESSION_REGISTRY: dict[str, list[dict[str, str]]] = {
    "electrostatics": [
        {"expression": "es.V", "description": "Electric potential field", "evaluation": "field"},
        {"expression": "es.normE", "description": "Electric field norm", "evaluation": "field_or_operator"},
        {"expression": "es.intWe", "description": "Total electric energy", "evaluation": "global"},
        {"expression": "2*es.intWe/V0^2", "description": "Energy-based capacitance estimate", "evaluation": "global"},
    ],
    "heat_transfer": [
        {"expression": "T", "description": "Temperature", "evaluation": "field"},
        {"expression": "ht.qx", "description": "Conductive heat flux x-component", "evaluation": "field_or_operator"},
        {"expression": "ht.Q", "description": "Heat source density", "evaluation": "field_or_operator"},
    ],
    "fluid_flow": [
        {"expression": "spf.U", "description": "Velocity magnitude", "evaluation": "field_or_operator"},
        {"expression": "p", "description": "Pressure", "evaluation": "field_or_operator"},
        {"expression": "spf.Re", "description": "Local Reynolds number when available", "evaluation": "field_or_operator"},
    ],
    "solid_mechanics": [
        {"expression": "solid.mises", "description": "von Mises stress", "evaluation": "field_or_operator"},
        {"expression": "solid.disp", "description": "Displacement magnitude", "evaluation": "field_or_operator"},
        {"expression": "solid.sx", "description": "Normal stress x-component", "evaluation": "field_or_operator"},
    ],
    "magnetic_fields": [
        {"expression": "mf.normB", "description": "Magnetic flux density norm", "evaluation": "field_or_operator"},
        {"expression": "mf.normH", "description": "Magnetic field norm", "evaluation": "field_or_operator"},
        {"expression": "mf.intWm", "description": "Stored magnetic energy when available", "evaluation": "global"},
        {"expression": "2*mf.intWm/I0^2", "description": "Energy-based inductance estimate", "evaluation": "global"},
    ],
}


def results_list_valid_expressions(physics_type: str = "general") -> dict:
    """Return curated expressions and evaluation hints for a physics family."""
    key = (physics_type or "general").strip().lower()
    expressions = EXPRESSION_REGISTRY.get(key, [])
    if not expressions:
        expressions = [
            {"expression": "T", "description": "Temperature if heat transfer exists", "evaluation": "field"},
            {"expression": "p", "description": "Pressure if a flow interface exists", "evaluation": "field_or_operator"},
        ]
    return {"success": True, "physics_type": key, "expressions": expressions, "count": len(expressions)}


def results_probe_expression(expression: str, unit: Optional[str] = None, dataset: Optional[str] = None) -> dict:
    """Try evaluating an expression and return a clear recommendation on failure."""
    if not expression.strip():
        return {"success": False, "error": "expression must not be empty."}
    result = mph_backend.results_global_evaluate(expression=expression, unit=unit, dataset=dataset)
    if result.get("success"):
        result["probe"] = {"valid": True, "recommended_next": "Use results_global_evaluate or results_evaluate for this expression."}
        return result
    result["probe"] = {
        "valid": False,
        "recommended_next": _recommend_expression_fix(expression),
    }
    return result


def results_create_max_operator(
    operator_name: str = "maxop1",
    entity_dimension: int = 3,
    selection: Optional[Sequence[int]] = None,
    named_selection: Optional[str] = None,
    component_name: str = "comp1",
    model_name: Optional[str] = None,
) -> dict:
    """Create a maximum coupling operator for field expressions."""
    return _create_coupling_operator("Maximum", operator_name, entity_dimension, selection, named_selection, component_name, model_name)


def results_create_average_operator(
    operator_name: str = "aveop1",
    entity_dimension: int = 3,
    selection: Optional[Sequence[int]] = None,
    named_selection: Optional[str] = None,
    component_name: str = "comp1",
    model_name: Optional[str] = None,
) -> dict:
    """Create an average coupling operator for field expressions."""
    return _create_coupling_operator("Average", operator_name, entity_dimension, selection, named_selection, component_name, model_name)


def results_evaluate_on_selection(
    expression: str,
    operator_name: str,
    unit: Optional[str] = None,
    dataset: Optional[str] = None,
) -> dict:
    """Evaluate an expression through an existing coupling operator."""
    if not expression.strip():
        return {"success": False, "error": "expression must not be empty."}
    if not operator_name.strip():
        return {"success": False, "error": "operator_name must not be empty."}
    wrapped = f"{operator_name}({expression})"
    result = mph_backend.results_global_evaluate(expression=wrapped, unit=unit, dataset=dataset)
    result["operator_expression"] = wrapped
    if not result.get("success"):
        result["recommendation"] = _recommend_expression_fix(wrapped)
    return result


def _create_coupling_operator(
    operator_type: str,
    operator_name: str,
    entity_dimension: int,
    selection: Optional[Sequence[int]],
    named_selection: Optional[str],
    component_name: str,
    model_name: Optional[str],
) -> dict:
    if entity_dimension not in {0, 1, 2, 3}:
        return {"success": False, "error": "entity_dimension must be one of 0, 1, 2, or 3."}
    if not operator_name.strip():
        return {"success": False, "error": "operator_name must not be empty."}
    model, error = current_model(model_name)
    if error:
        return error
    try:
        comp, comp_error = _component_for_operator(model, component_name)
        if comp_error:
            return {"success": False, "error": comp_error}
        definitions = comp.cpl()
        existing = list_tags(definitions)
        tag = operator_name if operator_name not in existing else unique_tag(existing, operator_name)
        operator = definitions.create(tag, operator_type)
        try:
            operator.selection().geom(entity_dimension)
        except Exception:
            pass
        selection_result = set_selection(operator, selection, named_selection=named_selection)
        return {
            "success": "error" not in selection_result,
            "operator": {
                "tag": tag,
                "type": operator_type,
                "component": component_name,
                "entity_dimension": entity_dimension,
                "selection": selection_result,
                "usage": f"{tag}(expression)",
            },
        }
    except Exception as exc:
        return {"success": False, "error": f"Failed to create {operator_type.lower()} operator: {exc}"}


def _component_for_operator(model, component_name: str):
    try:
        comp = model.java.component(component_name)
        if comp is not None:
            return comp, None
    except Exception:
        pass
    return None, f"Component '{component_name}' not found."


def _recommend_expression_fix(expression: str) -> str:
    lower = expression.lower()
    if lower.startswith("max(") or lower.startswith("min(") or lower.startswith("avg("):
        return "Create a COMSOL coupling operator first, then evaluate maxop1(expr) or aveop1(expr); plain max(expr) is often invalid in global evaluation."
    if lower in {"es.v", "es.norme", "t", "p", "spf.u", "solid.mises"} or "." in lower:
        return "This looks like a field expression. Evaluate it on a dataset, plot it, or create max/average operators for scalar global values."
    return "Check that the expression exists in the active physics interface and that a solution dataset is available."
