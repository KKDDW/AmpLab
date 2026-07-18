"""Study and solve tools for COMSOL models."""

from __future__ import annotations

from typing import Optional, Sequence

from .common import current_model, ensure_study, list_tags, safe_call, set_properties, to_jsonable, unique_tag


def study_list(model_name: Optional[str] = None) -> dict:
    """List studies and study steps."""
    model, error = current_model(model_name)
    if error:
        return error
    try:
        study_tags = to_jsonable(safe_call(model, "studies", [])) or []
        studies = []
        for tag in study_tags:
            item = {"tag": tag}
            try:
                study = model.java.study(tag)
                item["label"] = safe_call(study, "label", tag)
                item["steps"] = [
                    {"tag": step_tag, "label": safe_call(study.feature(step_tag), "label", step_tag), "type": safe_call(study.feature(step_tag), "getType", None)}
                    for step_tag in list_tags(study.feature())
                ]
            except Exception:
                pass
            studies.append(item)
        return {"success": True, "studies": studies, "count": len(studies)}
    except Exception as exc:
        return {"success": False, "error": f"Failed to list studies: {exc}"}


def study_create(
    study_name: str = "std1",
    label: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Create or return a study node."""
    model, error = current_model(model_name)
    if error:
        return error
    study, study_error = ensure_study(model, study_name=study_name, create=True)
    if study_error:
        return {"success": False, "error": study_error}
    try:
        if label:
            study.label(label)
    except Exception:
        pass
    return {"success": True, "study": study_name, "label": safe_call(study, "label", label or study_name)}


def study_create_stationary(
    study_name: str = "std1",
    step_tag: Optional[str] = None,
    physics_tags: Optional[Sequence[str]] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Create a stationary study step."""
    return _study_add_step("Stationary", study_name, step_tag, physics_tags, None, model_name)


def study_create_time_dependent(
    time_range: str,
    study_name: str = "std1",
    step_tag: Optional[str] = None,
    physics_tags: Optional[Sequence[str]] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Create a time dependent study step."""
    return _study_add_step("Transient", study_name, step_tag, physics_tags, {"tlist": time_range}, model_name)


def study_create_frequency_domain(
    frequencies: str,
    study_name: str = "std1",
    step_tag: Optional[str] = None,
    physics_tags: Optional[Sequence[str]] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Create a frequency domain study step."""
    return _study_add_step("Frequency", study_name, step_tag, physics_tags, {"plist": frequencies}, model_name)


def _study_add_step(
    step_type: str,
    study_name: str,
    step_tag: Optional[str],
    physics_tags: Optional[Sequence[str]],
    properties: Optional[dict],
    model_name: Optional[str],
) -> dict:
    model, error = current_model(model_name)
    if error:
        return error
    study, study_error = ensure_study(model, study_name=study_name, create=True)
    if study_error:
        return {"success": False, "error": study_error}
    try:
        prefix = {"Stationary": "stat", "Transient": "time", "Frequency": "freq"}.get(step_type, "step")
        tag = step_tag or unique_tag(list_tags(study.feature()), prefix)
        step = study.feature().create(tag, step_type)
        prop_result = set_properties(step, properties or {})
        activated: dict[str, bool] = {}
        activation_errors: dict[str, str] = {}
        if physics_tags:
            for physics_tag in physics_tags:
                activated[physics_tag], activation_errors[physics_tag] = _activate_physics(step, physics_tag)
        return {
            "success": not prop_result["failed"],
            "study": study_name,
            "step": {
                "tag": tag,
                "type": step_type,
                "properties": properties or {},
                "property_result": prop_result,
                "activated": activated,
                "activation_errors": {key: value for key, value in activation_errors.items() if value},
            },
        }
    except Exception as exc:
        return {"success": False, "error": f"Failed to create study step: {exc}"}


def study_solve(
    study_name: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Solve a study synchronously."""
    model, error = current_model(model_name)
    if error:
        return error
    wrapper_error = None
    java_study_name = study_name or _first_study_tag(model)
    if java_study_name:
        try:
            model.java.study(java_study_name).run()
            return {
                "success": True,
                "study": java_study_name,
                "message": "Solving completed through COMSOL Java study API.",
                "solutions": to_jsonable(safe_call(model, "solutions", [])),
                "problems": to_jsonable(safe_call(model, "problems", [])),
            }
        except Exception as exc:
            java_error = str(exc)
    else:
        java_error = "No study tag found."
    try:
        model.solve(study_name)
        return {
            "success": True,
            "study": study_name,
            "message": "Solving completed.",
            "java_error": java_error,
            "solutions": to_jsonable(safe_call(model, "solutions", [])),
            "problems": to_jsonable(safe_call(model, "problems", [])),
        }
    except Exception as exc:
        wrapper_error = str(exc)
    return {
        "success": False,
        "error": f"Failed to solve study through Java API: {java_error}; wrapper solve failed: {wrapper_error}",
        "study": study_name,
        "problems": to_jsonable(safe_call(model, "problems", [])),
    }


def solutions_list(model_name: Optional[str] = None) -> dict:
    """List solutions."""
    model, error = current_model(model_name)
    if error:
        return error
    try:
        solutions = to_jsonable(safe_call(model, "solutions", [])) or []
        return {"success": True, "solutions": solutions, "count": len(solutions)}
    except Exception as exc:
        return {"success": False, "error": f"Failed to list solutions: {exc}"}


def datasets_list(model_name: Optional[str] = None) -> dict:
    """List result datasets."""
    model, error = current_model(model_name)
    if error:
        return error
    try:
        datasets = to_jsonable(safe_call(model, "datasets", [])) or []
        return {"success": True, "datasets": datasets, "count": len(datasets)}
    except Exception as exc:
        return {"success": False, "error": f"Failed to list datasets: {exc}"}


def solver_configure_stationary(
    study_name: str = "std1",
    mode: str = "segregated",
    relative_tolerance: str = "1e-3",
    max_iterations: int = 50,
    damping: bool = True,
    model_name: Optional[str] = None,
) -> dict:
    """Configure a stationary solver sequence best-effort."""
    model, error = current_model(model_name)
    if error:
        return error
    try:
        sol_tag = _ensure_solver_for_study(model, study_name)
        sol = model.java.sol(sol_tag)
        properties = {
            "stol": relative_tolerance,
            "rtol": relative_tolerance,
            "maxiter": str(max_iterations),
            "maxiteractive": str(max_iterations),
            "dtech": "auto" if damping else "none",
        }
        applied = []
        failed = []
        for feature_tag in list_tags(sol.feature()):
            feature = sol.feature(feature_tag)
            prop_result = set_properties(feature, properties)
            if prop_result["applied"]:
                applied.append({"feature": feature_tag, "type": safe_call(feature, "getType", None), "property_result": prop_result})
            if prop_result["failed"]:
                failed.append({"feature": feature_tag, "type": safe_call(feature, "getType", None), "property_result": prop_result})
        mode_result = {}
        if mode.lower() == "segregated":
            mode_result = _try_add_segregated(sol)
        return {
            "success": bool(applied) or bool(mode_result.get("success")),
            "study": study_name,
            "solver": sol_tag,
            "mode": mode,
            "applied": applied,
            "failed": failed,
            "mode_result": mode_result,
            "message": "Solver configuration is best-effort; inspect failed property keys for COMSOL-version-specific settings.",
        }
    except Exception as exc:
        return {"success": False, "error": f"Failed to configure stationary solver: {exc}", "study": study_name}


def _first_study_tag(model) -> Optional[str]:
    try:
        tags = list_tags(model.java.study())
        return tags[0] if tags else None
    except Exception:
        return None


def _activate_physics(step, physics_tag: str) -> tuple[bool, str]:
    attempts = [
        ("activate", [physics_tag, "on"]),
        ("activate", [physics_tag, "true"]),
        ("activate", [physics_tag, "1"]),
        (f"activate/{physics_tag}", True),
        (f"activate/{physics_tag}", "on"),
        ("activate", [physics_tag]),
    ]
    errors = []
    for key, value in attempts:
        try:
            step.set(key, value)
            return True, ""
        except Exception as exc:
            errors.append(f"{key}={value}: {exc}")
    return False, "; ".join(errors)


def _ensure_solver_for_study(model, study_name: str) -> str:
    try:
        tags = list_tags(model.java.sol())
    except Exception:
        tags = []
    if tags:
        return tags[0]
    sol_tag = "sol1"
    sol = model.java.sol().create(sol_tag)
    try:
        sol.study(study_name)
    except Exception:
        pass
    try:
        sol.create("st1", "StudyStep")
        sol.feature("st1").set("study", study_name)
    except Exception:
        pass
    try:
        sol.create("v1", "Variables")
    except Exception:
        pass
    try:
        sol.create("s1", "Stationary")
    except Exception:
        pass
    return sol_tag


def _try_add_segregated(sol) -> dict:
    errors = []
    try:
        stationary_tag = None
        for tag in list_tags(sol.feature()):
            feature = sol.feature(tag)
            if safe_call(feature, "getType", "") == "Stationary":
                stationary_tag = tag
                break
        if not stationary_tag:
            return {"success": False, "error": "No Stationary solver feature found."}
        stationary = sol.feature(stationary_tag)
        existing = list_tags(stationary.feature())
        if "seg1" not in existing:
            stationary.feature().create("seg1", "Segregated")
        return {"success": True, "stationary_feature": stationary_tag, "segregated": "seg1"}
    except Exception as exc:
        errors.append(str(exc))
    return {"success": False, "error": "; ".join(errors)}
