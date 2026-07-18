"""Structured COMSOL automation backend using the mph package."""

from __future__ import annotations

import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Sequence, Union

from ..config import MODELS_DIR

try:
    import mph  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - tested via monkeypatchable state
    mph = None  # type: ignore


def _missing_message() -> str:
    return "Python package 'mph' is not installed in this environment."


_PORT_PATCHED = False


def _patch_parse_port() -> None:
    """让 mph 的端口解析兼容非英文 (中文) COMSOL server 输出。

    根本问题: 中文版 COMSOL server 启动时输出类似
        "COMSOL Multiphysics server 6.4 (构建版本: 293) 开始在端口 3638 上监听"
    而 mph.server.parse_port 的正则只认英文 "listening on port" 那种格式,
    中文行匹配不上 -> mph 读到下一行的 '#' 提示符 -> 报
    "Starting server failed: #"。这是必然故障, 不是偶发。

    修复: 包装原 parse_port。原正则先试; 失败则在含 'COMSOL' 的行里
    取最后一个 4-5 位数字当端口 (端口号在中英文输出里都是行内唯一的
    4-5 位数; 构建号 293 是 3 位, 版本号 6.4 也不足 4 位, 不会误取)。
    """
    global _PORT_PATCHED
    if _PORT_PATCHED or mph is None:
        return
    try:
        import re as _re
        from mph import server as _server  # type: ignore
    except Exception:
        return

    _orig_parse_port = _server.parse_port

    def _robust_parse_port(line: str):
        try:
            port = _orig_parse_port(line)
        except Exception:
            port = None
        if port:
            return port
        if not line or "COMSOL" not in line:
            return None
        nums = _re.findall(r"\d{4,5}", line)
        if nums:
            return int(nums[-1])
        return None

    _server.parse_port = _robust_parse_port
    _PORT_PATCHED = True


def _kill_stale_servers() -> None:
    """清理残留的 comsolmphserver 进程 (COMSOL 冷启动失败后可能挂着)。

    仅在启动失败重试前调用。此时本会话尚无有效 client, 因此杀掉所有
    comsolmphserver 是安全的 (不会误杀正在服务的 server)。best-effort。
    """
    try:
        import psutil  # type: ignore
    except Exception:
        return
    for proc in psutil.process_iter(["name"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if "comsolmphserver" in name:
                proc.kill()
        except Exception:
            continue


def is_available() -> bool:
    return mph is not None


def _safe_call(obj: Any, method: str, default: Any = None, *args: Any, **kwargs: Any) -> Any:
    try:
        func = getattr(obj, method)
        return func(*args, **kwargs)
    except Exception:
        return default


def _to_jsonable(value: Any) -> Any:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return float(value)
    except Exception:
        return str(value)


def _model_name(model: Any) -> str:
    name = _safe_call(model, "name")
    return str(name or "model")


def _model_file(model: Any) -> Optional[str]:
    value = _safe_call(model, "file")
    return str(value) if value else None


def _sanitize_name(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return clean[:80] or "model"


def _version_path(model_name: str) -> Path:
    base = _sanitize_name(Path(model_name).stem or model_name)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    directory = MODELS_DIR / base
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{base}_{stamp}.mph"


def _latest_path(model_name: str) -> Path:
    base = _sanitize_name(Path(model_name).stem or model_name)
    directory = MODELS_DIR / base
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{base}_latest.mph"


class MphSession:
    """Singleton session manager for mph."""

    _instance: Optional["MphSession"] = None

    def __new__(cls) -> "MphSession":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.client = None
            cls._instance.models = {}
            cls._instance.current_model = None
            cls._instance._lock = threading.RLock()
        return cls._instance

    def start(self, cores: Optional[int] = None, version: Optional[str] = None,
              retries: int = 3) -> dict:
        if mph is None:
            return {"success": False, "error": _missing_message()}
        # 兼容中文版 COMSOL server 输出 (根治 "Starting server failed: #")。
        _patch_parse_port()
        with self._lock:
            if self.client is not None:
                return self.clear_models("Existing mph client kept alive and models cleared.")
        # 中文版 COMSOL server 输出的端口行 mph 正则匹配不上 -> 读到 '#' 提示符
        # -> 报 "Starting server failed: #"。已由 _patch_parse_port() 修复 (在上面
        # 调用)。此处保留重试 + 清理残留进程, 兜底真正的瞬时冷启动故障。
        last_exc: Optional[Exception] = None
        for attempt in range(1, max(1, retries) + 1):
            try:
                # Momoi 修复: 用 mph.start() 而非 mph.Client()
                # mph.start() 会自动初始化完整的多物理场接口 (物理 + 流场 + 耦合)
                # 而 mph.Client() 只创建 client, 不加载物理接口, 导致 model.load() 时
                # "初始化物理场接口失败"
                client = mph.start(cores=cores, version=version)
                with self._lock:
                    self.client = client
                return {
                    "success": True,
                    "version": getattr(client, "version", None),
                    "cores": getattr(client, "cores", None),
                    "standalone": getattr(client, "standalone", None),
                    "attempts": attempt,
                }
            except Exception as exc:
                last_exc = exc
                if attempt < max(1, retries):
                    _kill_stale_servers()
                    time.sleep(2.0)
        return {"success": False,
                "error": f"Failed to start mph client after {max(1, retries)} attempts: {last_exc}"}

    def connect(self, port: int, host: str = "localhost") -> dict:
        if mph is None:
            return {"success": False, "error": _missing_message()}
        if self.client is not None:
            return {"success": False, "error": "mph client already exists. Disconnect or clear first."}
        try:
            self.client = mph.Client(port=port, host=host)
            return {"success": True, "host": host, "port": port, "version": getattr(self.client, "version", None)}
        except Exception as exc:
            return {"success": False, "error": f"Failed to connect mph client: {exc}"}

    def clear_models(self, message: str = "Session cleared.") -> dict:
        if self.client is None:
            self.models.clear()
            self.current_model = None
            return {"success": True, "message": "No active mph client."}
        try:
            self.client.clear()
        except Exception as exc:
            message = f"{message} Client clear reported: {exc}"
        self.models.clear()
        self.current_model = None
        return {"success": True, "message": message}

    def disconnect(self) -> dict:
        return self.clear_models("Session cleared; mph client kept alive for reuse.")

    def status(self) -> dict:
        start = _start_manager.status()
        if self.client is None:
            status = {"connected": False, "available": is_available(), "message": "No active mph session."}
            if start.get("task_id"):
                status["startup"] = start
            return status
        models = []
        for name, model in self.models.items():
            models.append({"name": name, "is_current": name == self.current_model, "file": _model_file(model)})
        status = {
            "connected": True,
            "available": is_available(),
            "version": getattr(self.client, "version", None),
            "cores": getattr(self.client, "cores", None),
            "standalone": getattr(self.client, "standalone", None),
            "models": models,
            "current_model": self.current_model,
        }
        if start.get("task_id"):
            status["startup"] = start
        return status

    def add_model(self, model: Any, set_current: bool = True) -> str:
        name = _model_name(model)
        self.models[name] = model
        if set_current or self.current_model is None:
            self.current_model = name
        return name

    def get_model(self, model_name: Optional[str] = None) -> Any:
        name = model_name or self.current_model
        if name is None:
            return None
        return self.models.get(name)


session = MphSession()


class StartTaskManager:
    """Best-effort background startup state for slow COMSOL cold starts."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._task: dict[str, Any] = {}

    def start_async(self, cores: Optional[int] = None, version: Optional[str] = None) -> dict:
        if mph is None:
            return {"success": False, "error": _missing_message()}
        with self._lock:
            if session.client is not None:
                return {"success": True, "ready": True, "status": "ready", "message": "mph client already active.", "mph_status": session.status()}
            if self._task.get("status") == "starting":
                return dict(self._task)
            task_id = uuid.uuid4().hex
            self._task = {
                "success": True,
                "task_id": task_id,
                "status": "starting",
                "ready": False,
                "cancel_requested": False,
                "cores": cores,
                "version": version,
                "started_at": time.time(),
                "elapsed_sec": 0.0,
                "result": None,
                "error": None,
            }
        thread = threading.Thread(target=self._run_start, args=(task_id, cores, version), name="comsol-mph-start", daemon=True)
        thread.start()
        return self.status(task_id)

    def _run_start(self, task_id: str, cores: Optional[int], version: Optional[str]) -> None:
        result = session.start(cores=cores, version=version)
        with self._lock:
            if self._task.get("task_id") != task_id:
                return
            elapsed = time.time() - float(self._task.get("started_at", time.time()))
            self._task["elapsed_sec"] = round(elapsed, 3)
            self._task["result"] = result
            self._task["ready"] = bool(result.get("success")) and session.client is not None
            self._task["status"] = "ready" if self._task["ready"] else "failed"
            self._task["error"] = result.get("error")

    def status(self, task_id: Optional[str] = None) -> dict:
        with self._lock:
            if not self._task:
                return {"success": True, "task_id": None, "status": "idle", "ready": session.client is not None}
            task = dict(self._task)
        if task_id and task.get("task_id") != task_id:
            return {"success": False, "error": f"Startup task not found: {task_id}", "task_id": task_id}
        task["elapsed_sec"] = round(time.time() - float(task.get("started_at", time.time())), 3)
        task["ready"] = bool(task.get("ready")) or session.client is not None
        if task["ready"] and task.get("status") == "starting":
            task["status"] = "ready"
        return task

    def cancel(self, task_id: Optional[str] = None) -> dict:
        with self._lock:
            if not self._task:
                return {"success": True, "status": "idle", "message": "No startup task to cancel."}
            if task_id and self._task.get("task_id") != task_id:
                return {"success": False, "error": f"Startup task not found: {task_id}", "task_id": task_id}
            self._task["cancel_requested"] = True
            if self._task.get("status") == "starting":
                self._task["status"] = "cancel_requested"
            return dict(self._task)


_start_manager = StartTaskManager()


def mph_start(cores: Optional[int] = None, version: Optional[str] = None) -> dict:
    return session.start(cores=cores, version=version)


def mph_start_async(cores: Optional[int] = None, version: Optional[str] = None) -> dict:
    return _start_manager.start_async(cores=cores, version=version)


def mph_start_status(task_id: Optional[str] = None) -> dict:
    return _start_manager.status(task_id=task_id)


def mph_cancel_start(task_id: Optional[str] = None) -> dict:
    return _start_manager.cancel(task_id=task_id)


def mph_connect(port: int, host: str = "localhost") -> dict:
    return session.connect(port=port, host=host)


def mph_status() -> dict:
    return session.status()


def mph_disconnect() -> dict:
    return session.disconnect()


def model_create(name: Optional[str] = None) -> dict:
    if session.client is None:
        return {"success": False, "error": "No active mph session. Start with mph_start first."}
    try:
        model = session.client.create(name)
        model_name = session.add_model(model)
        return {"success": True, "model": {"name": model_name, "is_current": True}}
    except Exception as exc:
        return {"success": False, "error": f"Failed to create model: {exc}"}


def model_load(file_path: str) -> dict:
    if session.client is None:
        return {"success": False, "error": "No active mph session. Start with mph_start first."}
    path = Path(file_path)
    if not path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}
    if path.suffix.lower() != ".mph":
        return {"success": False, "error": f"File must be a .mph model: {file_path}"}
    try:
        model = session.client.load(str(path.resolve()))
        name = session.add_model(model)
        return {"success": True, "model": {"name": name, "file": str(path.resolve()), "is_current": True}}
    except Exception as exc:
        return {"success": False, "error": f"Failed to load model: {exc}"}


def model_save(file_path: Optional[str] = None, model_name: Optional[str] = None) -> dict:
    model = session.get_model(model_name)
    if model is None:
        return {"success": False, "error": f"Model not found: {model_name or 'current model'}"}
    try:
        model.save(path=file_path)
        return {"success": True, "model": _model_name(model), "saved_to": file_path or _model_file(model)}
    except TypeError:
        try:
            if file_path:
                model.save(file_path)
            else:
                model.save()
            return {"success": True, "model": _model_name(model), "saved_to": file_path or _model_file(model)}
        except Exception as exc:
            return {"success": False, "error": f"Failed to save model: {exc}"}
    except Exception as exc:
        return {"success": False, "error": f"Failed to save model: {exc}"}


def model_save_version(description: Optional[str] = None, model_name: Optional[str] = None) -> dict:
    model = session.get_model(model_name)
    if model is None:
        return {"success": False, "error": f"Model not found: {model_name or 'current model'}"}
    name = _model_name(model)
    version_path = _version_path(name)
    latest_path = _latest_path(name)
    first = model_save(str(version_path), model_name=model_name)
    if not first.get("success"):
        return first
    latest = model_save(str(latest_path), model_name=model_name)
    return {
        "success": bool(latest.get("success")),
        "model": name,
        "version_path": str(version_path),
        "latest_path": str(latest_path),
        "description": description,
        "latest_save": latest,
    }


def model_list() -> dict:
    return {
        "success": True,
        "connected": session.client is not None,
        "models": [
            {"name": name, "is_current": name == session.current_model, "file": _model_file(model)}
            for name, model in session.models.items()
        ],
        "count": len(session.models),
        "current_model": session.current_model,
    }


def model_inspect(model_name: Optional[str] = None) -> dict:
    model = session.get_model(model_name)
    if model is None:
        return {"success": False, "error": f"Model not found: {model_name or 'current model'}"}
    sections = [
        "parameters",
        "functions",
        "components",
        "geometries",
        "selections",
        "physics",
        "multiphysics",
        "materials",
        "meshes",
        "studies",
        "solutions",
        "datasets",
        "plots",
        "exports",
        "modules",
        "problems",
    ]
    info = {"name": _model_name(model), "file": _model_file(model), "comsol_version": _safe_call(model, "version")}
    for section in sections:
        info[section] = _to_jsonable(_safe_call(model, section, default=[]))
    return {"success": True, "model": info}


def param_set(name: str, value: str, description: Optional[str] = None, model_name: Optional[str] = None) -> dict:
    if not re.match(r"^[A-Za-z_]\w*$", name or ""):
        return {"success": False, "error": "Parameter name must be a valid identifier."}
    model = session.get_model(model_name)
    if model is None:
        return {"success": False, "error": f"Model not found: {model_name or 'current model'}"}
    try:
        model.parameter(name, value)
        if description:
            model.description(name, description)
        return {"success": True, "parameter": name, "value": value, "description": description}
    except Exception as exc:
        return {"success": False, "error": f"Failed to set parameter: {exc}"}


def param_get(name: str, evaluate: bool = False, model_name: Optional[str] = None) -> dict:
    model = session.get_model(model_name)
    if model is None:
        return {"success": False, "error": f"Model not found: {model_name or 'current model'}"}
    try:
        return {
            "success": True,
            "parameter": name,
            "value": _to_jsonable(model.parameter(name, evaluate=evaluate)),
            "description": _safe_call(model, "description", "", name),
            "evaluated": evaluate,
        }
    except Exception as exc:
        return {"success": False, "error": f"Failed to get parameter: {exc}"}


def param_list(evaluate: bool = False, model_name: Optional[str] = None) -> dict:
    model = session.get_model(model_name)
    if model is None:
        return {"success": False, "error": f"Model not found: {model_name or 'current model'}"}
    try:
        params = model.parameters(evaluate=evaluate) or {}
        descriptions = _safe_call(model, "descriptions", default={}) or {}
        values = [
            {"name": name, "value": _to_jsonable(value), "description": descriptions.get(name, "")}
            for name, value in params.items()
        ]
        return {"success": True, "parameters": values, "count": len(values), "evaluated": evaluate}
    except Exception as exc:
        return {"success": False, "error": f"Failed to list parameters: {exc}"}


def param_remove(name: str, model_name: Optional[str] = None) -> dict:
    model = session.get_model(model_name)
    if model is None:
        return {"success": False, "error": f"Model not found: {model_name or 'current model'}"}
    try:
        model.java.param().remove(name)
        return {"success": True, "removed": name}
    except Exception as exc:
        return {"success": False, "error": f"Failed to remove parameter through Java API: {exc}"}


def results_evaluate(
    expression: Union[str, Sequence[str]],
    unit: Optional[str] = None,
    dataset: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    model = session.get_model(model_name)
    if model is None:
        return {"success": False, "error": f"Model not found: {model_name or 'current model'}"}
    attempted: list[dict[str, str]] = []
    direct = _evaluate_with_dataset_fallback(model, expression, unit, dataset)
    if direct.get("success"):
        return direct
    attempted.extend(direct.get("attempted_datasets", []))
    if not isinstance(expression, str):
        partial = []
        for item in expression:
            item_result = _evaluate_with_dataset_fallback(model, item, unit, dataset)
            partial.append(item_result)
        successes = [item for item in partial if item.get("success")]
        if successes:
            return {
                "success": True,
                "partial_success": len(successes) < len(partial),
                "expression": expression,
                "unit": unit,
                "dataset": successes[0].get("dataset"),
                "value": {str(item.get("expression")): item.get("value") for item in partial},
                "results": partial,
                "failed_expressions": [item.get("expression") for item in partial if not item.get("success")],
                "attempted_datasets": attempted,
            }
    first_error = attempted[0]["error"] if attempted else "unknown error"
    return {"success": False, "error": f"Failed to evaluate expression: {first_error}", "attempted_datasets": attempted}


def _evaluate_with_dataset_fallback(model: Any, expression: Union[str, Sequence[str]], unit: Optional[str], dataset: Optional[str]) -> dict:
    attempted: list[dict[str, str]] = []
    candidates = [dataset]
    if dataset is None:
        candidates.extend(_dataset_names(model))
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        try:
            result = model.evaluate(expression, unit=unit, dataset=candidate)
            payload = {
                "success": True,
                "expression": expression,
                "unit": unit,
                "dataset": candidate,
                "value": _to_jsonable(result),
                "shape": _to_jsonable(getattr(result, "shape", None)),
            }
            if candidate != dataset:
                payload["fallback"] = "dataset"
                payload["attempted_datasets"] = attempted
            return payload
        except Exception as exc:
            attempted.append({"dataset": key, "error": str(exc)})
    first_error = attempted[0]["error"] if attempted else "unknown error"
    return {"success": False, "expression": expression, "error": f"Failed to evaluate expression: {first_error}", "attempted_datasets": attempted}


def _dataset_names(model: Any) -> list[str]:
    names: list[str] = []
    try:
        names.extend(str(name) for name in model.datasets())
    except Exception:
        pass
    names.extend(_dataset_tags(model))
    return names


def _dataset_tags(model: Any) -> list[str]:
    try:
        tags = model.java.result().dataset().tags()
        return [str(tag) for tag in tags]
    except Exception:
        return []


def results_global_evaluate(
    expression: str,
    unit: Optional[str] = None,
    dataset: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    result = results_evaluate(expression, unit=unit, dataset=dataset, model_name=model_name)
    if not result.get("success"):
        return result
    value = result.get("value")
    while isinstance(value, list) and value:
        value = value[0]
    result["value"] = value
    return result


def results_plots_list(model_name: Optional[str] = None) -> dict:
    model = session.get_model(model_name)
    if model is None:
        return {"success": False, "error": f"Model not found: {model_name or 'current model'}"}
    try:
        plots = model.plots()
        return {"success": True, "plots": plots, "count": len(plots)}
    except Exception as exc:
        return {"success": False, "error": f"Failed to list plots: {exc}"}


def results_export_image(node_name: Optional[str] = None, file_path: Optional[str] = None, model_name: Optional[str] = None) -> dict:
    model = session.get_model(model_name)
    if model is None:
        return {"success": False, "error": f"Model not found: {model_name or 'current model'}"}
    try:
        model.export(node_name, file_path)
        return {"success": True, "node": node_name, "file": file_path}
    except Exception as exc:
        return {"success": False, "error": f"Failed to export image: {exc}"}

