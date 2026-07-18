"""Physics interface tools for COMSOL models."""

from __future__ import annotations

from typing import Any, Optional, Sequence

from .common import current_model, ensure_component, get_physics, list_tags, safe_call, set_properties, set_selection, to_jsonable, unique_tag


PHYSICS_CATALOG = {
    "electrostatics": {
        "type": "Electrostatics",
        "tag": "es",
        "label": "Electrostatics",
        "module": "ACDC_Module",
        "domain_default": True,
        "common_boundaries": ["Ground", "ElectricPotential", "Terminal", "ZeroCharge"],
        "result_expressions": ["es.V", "es.normE", "es.intWe"],
    },
    "heat_transfer": {
        "type": "HeatTransfer",
        "tag": "ht",
        "label": "Heat Transfer in Solids",
        "module": "Heat_Transfer_Module",
        "domain_default": True,
        "common_boundaries": ["TemperatureBoundary", "HeatFluxBoundary", "ConvectiveHeatFlux", "ThermalInsulation"],
        "result_expressions": ["T", "ht.qx", "ht.gradT"],
    },
    "laminar_flow": {
        "type": "LaminarFlow",
        "tag": "spf",
        "label": "Laminar Flow",
        "module": "CFD_Module",
        "domain_default": True,
        "common_boundaries": ["InletBoundary", "OutletBoundary", "Wall", "Symmetry"],
        "result_expressions": ["spf.U", "p", "u", "v", "w"],
    },
    "solid_mechanics": {
        "type": "SolidMechanics",
        "tag": "solid",
        "label": "Solid Mechanics",
        "module": "Structural_Mechanics_Module",
        "domain_default": True,
        "common_boundaries": ["Fixed", "Roller", "BoundaryLoad", "Displacement"],
        "result_expressions": ["solid.mises", "solid.disp", "solid.u", "solid.v", "solid.w"],
    },
    "electric_currents": {
        "type": "ConductiveMedia",
        "tag": "ec",
        "label": "Electric Currents",
        "module": "ACDC_Module",
        "domain_default": True,
        "common_boundaries": ["Ground", "ElectricPotential", "Terminal", "NormalCurrentDensity"],
        "result_expressions": ["ec.V", "ec.normJ", "ec.Qrh"],
    },
    "magnetic_fields": {
        "type": "InductionCurrents",
        "tag": "mf",
        "label": "Magnetic Fields",
        "module": "ACDC_Module",
        "domain_default": True,
        "common_boundaries": ["Coil", "ExternalCurrentDensity", "MagneticInsulation"],
        "result_expressions": ["mf.normB", "mf.normH", "mf.intWm"],
    },
    "darcy_law": {
        "type": "DarcysLaw",
        "tag": "dl",
        "label": "Darcy's Law",
        "module": "Subsurface_Flow_Module",
        "domain_default": True,
        "common_boundaries": ["Pressure", "MassFlux"],
        "result_expressions": ["dl.p", "dl.u", "dl.U"],
    },
    "general_form_pde": {
        "type": "GeneralFormPDE",
        "tag": "g",
        "label": "General Form PDE",
        "module": "COMSOL_Multiphysics",
        "domain_default": True,
        "common_boundaries": ["DirichletBoundary", "FluxBoundary"],
        "result_expressions": ["g.u", "u"],
    },
}


def physics_get_available() -> dict:
    """Return supported physics helpers and Java API type identifiers."""
    return {"success": True, "physics": PHYSICS_CATALOG, "count": len(PHYSICS_CATALOG)}


def physics_list(model_name: Optional[str] = None, component_name: Optional[str] = None) -> dict:
    """List physics interfaces."""
    model, error = current_model(model_name)
    if error:
        return error
    try:
        if component_name:
            comp, comp_error = ensure_component(model, component_name=component_name, create=False)
            if comp_error:
                return {"success": False, "error": comp_error}
            physics = list_tags(comp.physics())
        else:
            physics = to_jsonable(safe_call(model, "physics", [])) or []
        multiphysics = to_jsonable(safe_call(model, "multiphysics", [])) or []
        return {"success": True, "physics": physics, "multiphysics": multiphysics, "count": len(physics)}
    except Exception as exc:
        return {"success": False, "error": f"Failed to list physics: {exc}"}


def physics_add(
    physics_type: str,
    tag: Optional[str] = None,
    component_name: str = "comp1",
    geometry_name: str = "geom1",
    domains: Optional[Sequence[int]] = None,
    label: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Add a physics interface through COMSOL's Java API."""
    model, error = current_model(model_name)
    if error:
        return error
    comp, comp_error = ensure_component(model, component_name=component_name, create=True)
    if comp_error:
        return {"success": False, "error": comp_error}
    try:
        existing = list_tags(comp.physics())
        physics_tag = tag or _default_tag_for_type(physics_type, existing)
        geom_tag = _resolve_geometry_tag(comp, geometry_name)
        physics = comp.physics().create(physics_tag, _type_for_name(physics_type), geom_tag)
        if label:
            physics.label(label)
        selection = set_selection(physics, domains) if domains else {"type": "all", "selection": []}
        return {
            "success": True,
            "physics": {
                "tag": physics_tag,
                "type": _type_for_name(physics_type),
                "label": safe_call(physics, "label", label or physics_type),
                "component": component_name,
                "geometry": geom_tag,
                "selection": selection,
            },
        }
    except Exception as exc:
        return {"success": False, "error": f"Failed to add physics '{physics_type}': {exc}"}


def _default_tag_for_type(physics_type: str, existing: list[str]) -> str:
    for item in PHYSICS_CATALOG.values():
        if _same_physics_name(physics_type, item):
            tag = item["tag"]
            return tag if tag not in existing else unique_tag(existing, tag)
    return unique_tag(existing, "phys")


def _type_for_name(physics_type: str) -> str:
    for key, item in PHYSICS_CATALOG.items():
        if physics_type == key or _same_physics_name(physics_type, item):
            return str(item["type"])
    return physics_type


def _same_physics_name(value: str, item: dict[str, Any]) -> bool:
    normalized = _normalize_name(value)
    aliases = {str(item["type"]), str(item["label"]), str(item["tag"])}
    return normalized in {_normalize_name(alias) for alias in aliases}


def _normalize_name(value: str) -> str:
    return "".join(ch.lower() for ch in str(value) if ch.isalnum())


def _resolve_geometry_tag(comp: Any, geometry_name: str) -> str:
    try:
        geom = comp.geom(geometry_name)
        if geom is not None:
            return str(safe_call(geom, "tag", geometry_name) or geometry_name)
    except Exception:
        pass
    for tag in list_tags(comp.geom()):
        try:
            geom = comp.geom(tag)
        except Exception:
            continue
        if geometry_name in {tag, str(safe_call(geom, "label", tag) or tag)}:
            return tag
    raise ValueError(f"Geometry '{geometry_name}' not found in component '{safe_call(comp, 'tag', 'component')}'.")


def _add_named_physics(
    name: str,
    domains: Optional[Sequence[int]],
    component_name: str,
    model_name: Optional[str],
    geometry_name: str = "geom1",
) -> dict:
    item = PHYSICS_CATALOG[name]
    return physics_add(
        physics_type=item["type"],
        tag=item["tag"],
        component_name=component_name,
        geometry_name=geometry_name,
        domains=domains,
        label=item["label"],
        model_name=model_name,
    )


def physics_add_electrostatics(
    domains: Optional[Sequence[int]] = None,
    component_name: str = "comp1",
    geometry_name: str = "geom1",
    model_name: Optional[str] = None,
) -> dict:
    """Add Electrostatics physics."""
    return _add_named_physics("electrostatics", domains, component_name, model_name, geometry_name)


def physics_add_heat_transfer(
    domains: Optional[Sequence[int]] = None,
    component_name: str = "comp1",
    geometry_name: str = "geom1",
    model_name: Optional[str] = None,
) -> dict:
    """Add Heat Transfer in Solids physics."""
    return _add_named_physics("heat_transfer", domains, component_name, model_name, geometry_name)


def physics_add_laminar_flow(
    domains: Optional[Sequence[int]] = None,
    component_name: str = "comp1",
    geometry_name: str = "geom1",
    model_name: Optional[str] = None,
) -> dict:
    """Add Laminar Flow physics."""
    return _add_named_physics("laminar_flow", domains, component_name, model_name, geometry_name)


def physics_add_solid_mechanics(
    domains: Optional[Sequence[int]] = None,
    component_name: str = "comp1",
    geometry_name: str = "geom1",
    model_name: Optional[str] = None,
) -> dict:
    """Add Solid Mechanics physics."""
    return _add_named_physics("solid_mechanics", domains, component_name, model_name, geometry_name)


def physics_add_magnetic_fields(
    domains: Optional[Sequence[int]] = None,
    component_name: str = "comp1",
    geometry_name: str = "geom1",
    model_name: Optional[str] = None,
) -> dict:
    """Add Magnetic Fields physics through the ACDC InductionCurrents interface."""
    return _add_named_physics("magnetic_fields", domains, component_name, model_name, geometry_name)


def physics_add_general_form_pde(
    domains: Optional[Sequence[int]] = None,
    component_name: str = "comp1",
    geometry_name: str = "geom1",
    tag: str = "g",
    model_name: Optional[str] = None,
) -> dict:
    """Add General Form PDE physics."""
    item = PHYSICS_CATALOG["general_form_pde"]
    return physics_add(
        physics_type=item["type"],
        tag=tag,
        component_name=component_name,
        geometry_name=geometry_name,
        domains=domains,
        label=item["label"],
        model_name=model_name,
    )


def physics_add_darcy_law(
    domains: Optional[Sequence[int]] = None,
    component_name: str = "comp1",
    geometry_name: str = "geom1",
    tag: str = "dl",
    model_name: Optional[str] = None,
) -> dict:
    """Add Darcy's Law physics."""
    item = PHYSICS_CATALOG["darcy_law"]
    return physics_add(
        physics_type=item["type"],
        tag=tag,
        component_name=component_name,
        geometry_name=geometry_name,
        domains=domains,
        label=item["label"],
        model_name=model_name,
    )


def darcy_set_porous_medium_properties(
    physics_tag: str = "dl",
    domains: Optional[Sequence[int]] = None,
    permeability: Optional[Any] = None,
    porosity: Optional[Any] = None,
    dynamic_viscosity: Optional[Any] = None,
    density: Optional[Any] = None,
    component_name: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Configure Darcy porous medium properties on the physics feature."""
    model, error = current_model(model_name)
    if error:
        return error
    physics, physics_error = get_physics(model, physics_tag, component_name)
    if physics_error:
        return {"success": False, "error": physics_error}
    properties: dict[str, Any] = {}
    if permeability is not None:
        properties.update(
            {
                "kappa_mat": "userdef",
                "kappa": permeability,
                "K_mat": "userdef",
                "K": permeability,
                "permeability_mat": "userdef",
                "permeability": permeability,
            }
        )
    if porosity is not None:
        properties.update(
            {
                "epsilon_mat": "userdef",
                "epsilon": porosity,
                "epsilon_p_mat": "userdef",
                "epsilon_p": porosity,
                "porosity_mat": "userdef",
                "porosity": porosity,
            }
        )
    if dynamic_viscosity is not None:
        properties.update(
            {
                "mu_mat": "userdef",
                "mu": dynamic_viscosity,
                "eta_mat": "userdef",
                "eta": dynamic_viscosity,
                "dynamicviscosity_mat": "userdef",
                "dynamicviscosity": dynamic_viscosity,
            }
        )
    if density is not None:
        properties.update(
            {
                "rho_mat": "userdef",
                "rho": density,
                "density_mat": "userdef",
                "density": density,
            }
        )
    if not properties:
        return {"success": False, "error": "Provide at least one Darcy property."}
    applied_features = []
    feature_tags = list_tags(physics.feature())
    candidate_tags = feature_tags or []
    if "dlm1" not in candidate_tags:
        candidate_tags.append("dlm1")
    if "fmp1" not in candidate_tags:
        candidate_tags.append("fmp1")
    for feature_tag in candidate_tags:
        try:
            feature = physics.feature(feature_tag)
        except Exception:
            continue
        prop_result = set_properties(feature, properties)
        selection = set_selection(feature, domains) if domains else {"type": "all", "selection": []}
        applied_features.append(
            {
                "tag": feature_tag,
                "type": safe_call(feature, "getType", None),
                "label": safe_call(feature, "label", feature_tag),
                "selection": selection,
                "property_result": prop_result,
            }
        )
    if not applied_features:
        return {
            "success": False,
            "error": "No configurable Darcy feature was found under the physics interface.",
            "physics": physics_tag,
            "available_features": feature_tags,
            "requested_properties": to_jsonable(properties),
        }
    any_applied = any(item["property_result"]["applied"] for item in applied_features)
    validation = _validate_darcy_property_application(
        applied_features,
        need_permeability=permeability is not None,
        need_porosity=porosity is not None,
        need_dynamic_viscosity=dynamic_viscosity is not None,
        need_density=density is not None,
    )
    return {
        "success": any_applied and validation["success"],
        "physics": physics_tag,
        "requested_properties": to_jsonable(properties),
        "features": applied_features,
        "validation": validation,
        "message": "Set Darcy properties on physics features; inspect failed keys if COMSOL still reports unresolved material properties.",
    }


def _validate_darcy_property_application(
    applied_features: list[dict[str, Any]],
    *,
    need_permeability: bool,
    need_porosity: bool,
    need_dynamic_viscosity: bool,
    need_density: bool,
) -> dict:
    applied_keys: set[str] = set()
    for item in applied_features:
        applied_keys.update(item.get("property_result", {}).get("applied", {}).keys())
    required_groups = {
        "permeability": (need_permeability, ({"kappa", "K", "permeability"}, {"kappa_mat", "K_mat", "permeability_mat"})),
        "porosity": (need_porosity, ({"epsilon", "epsilon_p", "porosity"}, {"epsilon_mat", "epsilon_p_mat", "porosity_mat"})),
        "dynamic_viscosity": (need_dynamic_viscosity, ({"mu", "eta", "dynamicviscosity"}, {"mu_mat", "eta_mat", "dynamicviscosity_mat"})),
        "density": (need_density, ({"rho", "density"}, {"rho_mat", "density_mat"})),
    }
    missing: dict[str, list[str]] = {}
    confirmed: dict[str, list[str]] = {}
    for group, (needed, (value_keys, source_keys)) in required_groups.items():
        if not needed:
            continue
        found_value = sorted(applied_keys & value_keys)
        found_source = sorted(applied_keys & source_keys)
        confirmed[group] = found_value + found_source
        if not found_value:
            missing.setdefault(group, []).append("value")
        if not found_source:
            missing.setdefault(group, []).append("source_userdef")
    return {"success": not missing, "confirmed": confirmed, "missing": missing}


def heat_transfer_add_heat_source(
    physics_tag: str = "ht",
    domains: Optional[Sequence[int]] = None,
    heat_source: Any = "ec.Qrh",
    feature_tag: Optional[str] = None,
    component_name: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Add a domain heat source to a Heat Transfer physics interface."""
    model, error = current_model(model_name)
    if error:
        return error
    physics, physics_error = get_physics(model, physics_tag, component_name)
    if physics_error:
        return {"success": False, "error": physics_error}
    existing = list_tags(physics.feature())
    tag = feature_tag or unique_tag(existing, "hs")
    errors: list[str] = []
    for feature_type in ("HeatSource", "DomainHeatSource"):
        try:
            feature = physics.feature().create(tag, feature_type, 2)
            selection = set_selection(feature, domains) if domains else {"type": "all", "selection": []}
            prop_result = set_properties(feature, {"Q0": heat_source, "Q": heat_source})
            return {
                "success": "error" not in selection and bool(prop_result["applied"]),
                "heat_source": {
                    "tag": tag,
                    "type": feature_type,
                    "physics": physics_tag,
                    "domains": [int(domain) for domain in domains] if domains else [],
                    "selection": selection,
                    "heat_source": to_jsonable(heat_source),
                    "property_result": prop_result,
                },
            }
        except Exception as exc:
            errors.append(f"{feature_type}: {exc}")
            try:
                physics.feature().remove(tag)
            except Exception:
                pass
    return {"success": False, "error": "Failed to add heat source: " + "; ".join(errors)}


def multiphysics_list(component_name: str = "comp1", model_name: Optional[str] = None) -> dict:
    """List multiphysics couplings in a component."""
    model, error = current_model(model_name)
    if error:
        return error
    comp, comp_error = ensure_component(model, component_name=component_name, create=False)
    if comp_error:
        return {"success": False, "error": comp_error}
    try:
        tags = list_tags(comp.multiphysics())
        couplings = []
        for tag in tags:
            coupling = comp.multiphysics(tag)
            couplings.append({"tag": tag, "label": safe_call(coupling, "label", tag), "type": safe_call(coupling, "getType", None)})
        return {"success": True, "component": component_name, "multiphysics": couplings, "count": len(couplings)}
    except Exception as exc:
        return {"success": False, "error": f"Failed to list multiphysics couplings: {exc}"}


def multiphysics_add(
    coupling_type: str,
    tag: Optional[str] = None,
    component_name: str = "comp1",
    physics_tags: Optional[Sequence[str]] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Add a multiphysics coupling through COMSOL's Java API."""
    model, error = current_model(model_name)
    if error:
        return error
    comp, comp_error = ensure_component(model, component_name=component_name, create=False)
    if comp_error:
        return {"success": False, "error": comp_error}
    try:
        existing = list_tags(comp.multiphysics())
        coupling_tag = tag or unique_tag(existing, "mult")
        coupling = comp.multiphysics().create(coupling_tag, coupling_type, "geom1", 2)
        prop_result = _configure_coupling_physics(coupling, physics_tags)
        return {
            "success": True,
            "multiphysics": {
                "tag": coupling_tag,
                "type": coupling_type,
                "label": safe_call(coupling, "label", coupling_type),
                "component": component_name,
                "physics_tags": list(physics_tags or []),
                "property_result": prop_result,
            },
        }
    except Exception as exc:
        return {"success": False, "error": f"Failed to add multiphysics coupling '{coupling_type}': {exc}"}


def multiphysics_add_electromagnetic_heating(
    electric_physics: str = "ec",
    heat_physics: str = "ht",
    component_name: str = "comp1",
    model_name: Optional[str] = None,
) -> dict:
    """Add an electromagnetic/Joule heating coupling if available."""
    attempts = []
    for coupling_type in ("ElectromagneticHeating", "JouleHeating", "ElectromagneticHeatSource"):
        result = multiphysics_add(
            coupling_type=coupling_type,
            tag="emh1",
            component_name=component_name,
            physics_tags=[electric_physics, heat_physics],
            model_name=model_name,
        )
        attempts.append({"type": coupling_type, "success": bool(result.get("success")), "error": result.get("error")})
        if result.get("success"):
            result["attempts"] = attempts
            return result
    return {"success": False, "error": "No electromagnetic heating coupling type could be created.", "attempts": attempts}


def _configure_coupling_physics(coupling: Any, physics_tags: Optional[Sequence[str]]) -> dict:
    if not physics_tags:
        return {"applied": {}, "failed": {}}
    properties: dict[str, Any] = {}
    if len(physics_tags) >= 1:
        properties.update({"EMHeatSource": physics_tags[0], "ElectricCurrents": physics_tags[0], "emhsrc": physics_tags[0]})
    if len(physics_tags) >= 2:
        properties.update({"HeatTransfer": physics_tags[1], "ht": physics_tags[1]})
    return set_properties(coupling, properties)


def physics_list_features(
    physics_tag: str,
    component_name: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """List features under a physics interface."""
    model, error = current_model(model_name)
    if error:
        return error
    physics, physics_error = get_physics(model, physics_tag, component_name)
    if physics_error:
        return {"success": False, "error": physics_error}
    try:
        features = []
        for tag in list_tags(physics.feature()):
            feature = physics.feature(tag)
            features.append({"tag": tag, "label": safe_call(feature, "label", tag), "type": safe_call(feature, "getType", None)})
        return {"success": True, "physics": physics_tag, "features": features, "count": len(features)}
    except Exception as exc:
        return {"success": False, "error": f"Failed to list physics features: {exc}"}


def physics_feature_info(
    physics_tag: str,
    feature_tag: str,
    component_name: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Return best-effort feature metadata, including property names and current values."""
    model, error = current_model(model_name)
    if error:
        return error
    physics, physics_error = get_physics(model, physics_tag, component_name)
    if physics_error:
        return {"success": False, "error": physics_error}
    try:
        feature = physics.feature(feature_tag)
    except Exception as exc:
        return {"success": False, "error": f"Feature '{feature_tag}' not found under physics '{physics_tag}': {exc}"}
    properties = _node_properties(feature)
    return {
        "success": True,
        "physics": physics_tag,
        "feature": {
            "tag": feature_tag,
            "label": safe_call(feature, "label", feature_tag),
            "type": safe_call(feature, "getType", None),
            "properties": properties,
        },
    }


def _node_properties(node: Any) -> dict[str, Any]:
    names = []
    for method in ("properties", "getProperties"):
        try:
            names = [str(name) for name in getattr(node, method)()]
            if names:
                break
        except Exception:
            pass
    values: dict[str, Any] = {}
    for name in names:
        try:
            values[name] = to_jsonable(node.get(name))
        except Exception as exc:
            values[name] = {"error": str(exc)}
    return values


def physics_remove(
    physics_tag: str,
    component_name: str = "comp1",
    model_name: Optional[str] = None,
) -> dict:
    """Remove a physics interface."""
    model, error = current_model(model_name)
    if error:
        return error
    comp, comp_error = ensure_component(model, component_name=component_name, create=False)
    if comp_error:
        return {"success": False, "error": comp_error}
    try:
        comp.physics().remove(physics_tag)
        return {"success": True, "removed": physics_tag, "component": component_name}
    except Exception as exc:
        return {"success": False, "error": f"Failed to remove physics '{physics_tag}': {exc}"}
