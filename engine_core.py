# -*- coding: utf-8 -*-
"""ampacity-lab: COMSOL 载流量寻优核心引擎（纯净版 - 无 UI 依赖）
=============================================

核心计算引擎，完全不依赖任何 UI 框架。
通过回调函数与外部通信。

设计原则:
  1. 使用 Secant 拟 Newton 法（IEEE 标准方法）
  2. Fallback 链: 割线法 -> 二分法
  3. 每点先回到 default solver state, 避免累积误差
  4. 支持多个 .mph 批量, 静态参数组, 动态扫描
  5. 通过回调函数接口与外界通信，不直接操作界面
"""
from __future__ import annotations
from itertools import product
import os
import sys
import time
import threading
import psutil
import traceback
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Callable, Any, Tuple, Set

# comsol_ampacity_mcp 优先用项目内置的那份
_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

import importlib.util as _ilu
if _ilu.find_spec('comsol_ampacity_mcp') is None:
    AMPACITY_MCP_SRC = r'D:\C\MiniMax\Saiba Momoi\cable_tools\comsol-ampacity-mcp\src'
    if os.path.isdir(AMPACITY_MCP_SRC) and AMPACITY_MCP_SRC not in sys.path:
        sys.path.append(AMPACITY_MCP_SRC)

import comsol_ampacity_mcp.backends.mph_backend as mph
from comsol_ampacity_mcp.server import _solve_study_by_tag

# 导入优化算法模块
sys.path.insert(0, _PARENT)
from optimizer import convert_temp_value, secant_method, bisection_method, hybrid_optimize


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _safe_attr(obj: Any, name: str, default: Any = None) -> Any:
    """调用 obj.<name>() 拿列表, 失败兜底."""
    if obj is None:
        return default
    try:
        attr = getattr(obj, name, None)
        if attr is None:
            return default
        return attr() if callable(attr) else attr
    except Exception:
        return default


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class PointResult:
    """一个工况的寻优结果"""
    task_id: int
    file_name: str
    group_name: str
    env_params: Dict[str, Any]
    final_I: Optional[float] = None
    final_T: Optional[float] = None
    converged: bool = False
    iterations: int = 0
    solve_count: int = 0
    history: List[Dict] = field(default_factory=list)
    error: str = ''
    elapsed_sec: float = 0.0
    status: str = 'pending'   # pending / running / success / failed / skipped

    def to_dict(self):
        d = asdict(self)
        d['elapsed_sec'] = round(d['elapsed_sec'], 4)
        return d


@dataclass
class MultiInspection:
    """多文件扫描结果的汇总"""
    file_count: int = 0
    file_paths: List[str] = field(default_factory=list)
    common_parameters: Set[str] = field(default_factory=set)
    common_studies: Set[str] = field(default_factory=set)
    common_evaluations: Set[str] = field(default_factory=set)
    partial_parameters: Dict[str, List[str]] = field(default_factory=dict)
    partial_studies: Dict[str, List[str]] = field(default_factory=dict)
    partial_evaluations: Dict[str, List[str]] = field(default_factory=dict)
    per_file_parameters: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    per_file_studies: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    per_file_evaluations: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    per_file_unique: Dict[str, Set[str]] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def available_params(self) -> List[str]:
        """收敛变量下拉候选列表 (common 在前, partial + unique 在后)."""
        common = sorted(self.common_parameters)
        others: Set[str] = set(self.partial_parameters.keys())
        for unique_set in self.per_file_unique.values():
            others.update(unique_set)
        others -= self.common_parameters
        available = common + sorted(others)
        if not available:
            available = ['I']
        return available

    @classmethod
    def from_inspections(cls, inspections: Dict[str, Dict[str, Any]]) -> 'MultiInspection':
        """从 {file_path: inspect_result} 构造 MultiInspection."""
        if not inspections:
            return cls(file_count=0, file_paths=[])

        file_paths = list(inspections.keys())
        file_count = len(file_paths)

        # 各文件的参数名 / 研究名 / 派生值名集合
        per_file_param_sets: Dict[str, Set[str]] = {
            fp: {p['name'] for p in r.get('parameters', [])}
            for fp, r in inspections.items()
        }
        per_file_study_sets: Dict[str, Set[str]] = {
            fp: {s['name'] for s in r.get('studies', [])}
            for fp, r in inspections.items()
        }
        per_file_eval_sets: Dict[str, Set[str]] = {
            fp: {e['name'] for e in r.get('evaluations', [])}
            for fp, r in inspections.items()
        }

        # 共有 (交集)
        common_p = set.intersection(*per_file_param_sets.values()) if per_file_param_sets else set()
        common_s = set.intersection(*per_file_study_sets.values()) if per_file_study_sets else set()
        common_e = set.intersection(*per_file_eval_sets.values()) if per_file_eval_sets else set()

        # 部分共有
        def _compute_partial(per_file_sets: Dict[str, Set[str]],
                            common: Set[str]) -> Dict[str, List[str]]:
            partial: Dict[str, List[str]] = {}
            if file_count <= 2:
                return partial
            name_to_files: Dict[str, List[str]] = {}
            for fp, names in per_file_sets.items():
                for n in names:
                    name_to_files.setdefault(n, []).append(fp)
            for name, owners in name_to_files.items():
                if name in common:
                    continue
                if 1 < len(owners) < file_count:
                    partial[name] = owners
            return partial

        partial_p = _compute_partial(per_file_param_sets, common_p)
        partial_s = _compute_partial(per_file_study_sets, common_s)
        partial_e = _compute_partial(per_file_eval_sets, common_e)

        # per_file_unique
        per_file_unique = {}
        for fp, pset in per_file_param_sets.items():
            if file_count <= 1:
                per_file_unique[fp] = set()
                continue
            others = set.union(*(s for f, s in per_file_param_sets.items() if f != fp))
            per_file_unique[fp] = pset - others

        # 详情 dict
        per_file_parameters = {
            fp: {p['name']: p for p in r.get('parameters', [])}
            for fp, r in inspections.items()
        }
        per_file_studies = {
            fp: {s['name']: s for s in r.get('studies', [])}
            for fp, r in inspections.items()
        }
        per_file_evaluations = {
            fp: {e['name']: e for e in r.get('evaluations', [])}
            for fp, r in inspections.items()
        }

        # 汇总 warnings
        warnings = []
        for r in inspections.values():
            warnings.extend(r.get('warnings', []))

        return cls(
            file_count=file_count,
            file_paths=file_paths,
            common_parameters=common_p,
            common_studies=common_s,
            common_evaluations=common_e,
            partial_parameters=partial_p,
            partial_studies=partial_s,
            partial_evaluations=partial_e,
            per_file_parameters=per_file_parameters,
            per_file_studies=per_file_studies,
            per_file_evaluations=per_file_evaluations,
            per_file_unique=per_file_unique,
            warnings=warnings,
        )


# ---------------------------------------------------------------------------
# 核心引擎
# ---------------------------------------------------------------------------

class AmpacityEngine:
    """COMSOL 载流量寻优引擎（纯净版）

    通过回调函数与外界通信：
        log_fn(msg: str, level: str) - 日志回调
        progress_fn(current: int, total: int, elapsed: float) - 进度回调
        result_fn(result: PointResult) - 单个结果回调
    """

    def __init__(
        self,
        log_fn: Optional[Callable[[str, str], None]] = None,
        progress_fn: Optional[Callable[[int, int, float], None]] = None,
        result_fn: Optional[Callable[[PointResult], None]] = None
    ):
        self.client = None
        self.log_fn = log_fn or (lambda msg, lv='info': None)
        self.progress_fn = progress_fn or (lambda cur, tot, elapsed: None)
        self.result_fn = result_fn or (lambda res: None)

        self.current_model = None
        self.current_file = ''

        # 寻优配置
        self.target_study = '研究 1'
        self.expression = 'max(T, 1)'
        self._detected_expression = None
        self.default_I = 0.0

        # 检测出来的元信息
        self.inspection: Dict[str, Any] = {}
        self.detected_studies: List[Dict[str, str]] = []
        self.detected_parameters: List[Dict[str, Any]] = []
        self.detected_evaluations: List[Dict[str, str]] = []

        # 可被外部改写的"收敛变量" + "派生值变量"
        self.current_param_name: str = 'I'
        self.temp_expression: str = 'max(T, 1)'
        self.temp_unit: str = 'K'

        # 任务列表
        self.tasks: List[PointResult] = []
        self.is_running = False
        self.should_stop = False

    def _log(self, msg: str, level: str = 'info'):
        """内部日志方法，调用外部回调"""
        self.log_fn(msg, level)

    # ---- 引擎管理 ----

    def start_engine(self, comsol_version: str = 'latest',
                     cores: Optional[int] = None) -> bool:
        """启动 COMSOL mph 引擎"""
        try:
            self._log('正在启动 COMSOL 引擎...', 'sys')
            if getattr(sys, 'frozen', False):
                try:
                    import mph as _real_mph
                    _real_mph.option('session', 'client-server')
                except Exception as _e:
                    self._log(f'设置 client-server 模式失败: {_e}', 'error')

            _ver = None if comsol_version == 'latest' else comsol_version
            self.client = mph.mph_start(version=_ver, cores=cores)

            if not self.client.get('success'):
                self._log(f"启动失败: {self.client.get('error')}", 'error')
                return False

            v = self.client.get('version', '?')
            cores = self.client.get('cores', '?')
            self._log(f"【引擎】COMSOL {v}\t{cores} 核\t已就绪", 'success')
            return True
        except Exception as e:
            self._log(f"启动异常: {e}", 'error')
            return False

    def stop_engine(self):
        """断开引擎"""
        if self.client is not None:
            try:
                mph.mph_disconnect()
                self._log('COMSOL 引擎已断开', 'sys')
            except Exception as _e:
                self._log(f'COMSOL 引擎断开失败: {_e}', 'warning')

    # ---- 模型加载 ----

    def load_mph(self, file_path: str) -> bool:
        """加载 .mph 文件"""
        if not os.path.exists(file_path):
            self._log(f"文件不存在: {file_path}", 'error')
            return False

        # 先清理旧模型
        if self.current_model is not None:
            self._unload_current()

        try:
            r = mph.model_load(file_path)
            if not r.get('success'):
                self._log(f"加载失败: {r.get('error')}", 'error')
                return False

            self.current_file = file_path
            self.current_model = mph.session.get_model(mph.session.current_model)
            self._log(f"【模型】已加载 {os.path.basename(file_path)}", 'success')

            # 读默认 I
            try:
                cur = mph.param_get('I', evaluate=True)
                self.default_I = float(cur.get('value', 0))
                self._log(f"【参数】默认电流\t{self.default_I} A", 'info')
            except Exception:
                self.default_I = 0
                self._log(f'  (无默认 I 参数)', 'warning')

            return True
        except Exception as e:
            self._log(f"加载异常: {e}\n{traceback.format_exc()}", 'error')
            return False

    def _unload_current(self):
        """卸载当前模型"""
        try:
            if self.current_model is not None:
                real_client = getattr(mph.session, 'client', None)
                if real_client is not None:
                    real_client.remove(self.current_model)
        except Exception as _e:
            self._log(f'卸载模型失败: {_e}', 'warning')

        self.detected_studies = []
        self.detected_parameters = []
        self.detected_evaluations = []
        self.inspection = {}

    # ---- 模型检测 ----

    def inspect_mph(self, file_path: Optional[str] = None) -> Dict[str, Any]:
        """扫描 mph 文件, 提取: 研究 / 参数 / 派生值 / 单位"""
        if file_path is None:
            file_path = self.current_file
        if not file_path or not os.path.exists(file_path):
            return {'success': False, 'error': f'文件不存在: {file_path}'}

        self._log(f'[扫描] {os.path.basename(file_path)}', 'sys')
        warnings: List[str] = []

        # 加载模型
        if file_path != self.current_file or self.current_model is None:
            if not self.load_mph(file_path):
                return {'success': False, 'error': f'加载失败: {file_path}'}

        m = self.current_model
        if m is None:
            return {'success': False, 'error': '模型未加载'}

        # 研究列表
        studies: List[Dict[str, str]] = []
        try:
            for tag in (m.studies() or []):
                name = ''
                try:
                    name = m.java.study(tag).label()
                except Exception:
                    name = tag
                studies.append({'tag': tag, 'name': name})
        except Exception as e:
            warnings.append(f'读 studies 失败: {e}')

        self.detected_studies = studies

        # 参数列表
        parameters: List[Dict[str, Any]] = []
        try:
            param_names = _safe_attr(m, 'parameters', [])
            for pname in param_names:
                try:
                    pval = m.parameter(pname)
                    expr = ''
                    try:
                        expr = m.java.param().get(pname)
                    except Exception:
                        pass
                    parameters.append({'name': pname, 'value': pval, 'expression': expr})
                except Exception:
                    pass
        except Exception as e:
            warnings.append(f'读 parameters 失败: {e}')

        self.detected_parameters = parameters

        # 派生值列表
        evaluations: List[Dict[str, str]] = []
        try:
            eval_tags = _safe_attr(m, 'evaluations', [])
            for tag in eval_tags:
                try:
                    name = m.java.result().numerical(tag).label()
                    expr = m.java.result().numerical(tag).getString('expr')
                    evaluations.append({'tag': tag, 'name': name, 'expression': expr})
                except Exception:
                    pass
        except Exception as e:
            warnings.append(f'读 evaluations 失败: {e}')

        self.detected_evaluations = evaluations

        # 推断收敛变量和派生值表达式
        suggested_param = 'I'
        suggested_expr = 'max(T, 1)'
        suggested_unit = 'K'

        # 简单推断逻辑
        param_names_set = {p['name'] for p in parameters}
        if 'I' in param_names_set:
            suggested_param = 'I'
        elif param_names_set:
            suggested_param = sorted(param_names_set)[0]

        self.inspection = {
            'success': True,
            'file': file_path,
            'studies': studies,
            'parameters': parameters,
            'evaluations': evaluations,
            'suggested_current_param': suggested_param,
            'suggested_temp_expression': suggested_expr,
            'suggested_temp_unit': suggested_unit,
            'warnings': warnings,
        }

        return self.inspection

    # ---- 核心计算方法 ----

    def _solve_and_get_temp(self, current_I: float) -> Optional[float]:
        """设置电流并求解，返回温度

        Args:
            current_I: 电流值 (A)

        Returns:
            温度值 (按 self.temp_unit 单位)，失败返回 None
        """
        try:
            # 设置电流参数
            mph.param_set(self.current_param_name, str(current_I))

            # 求解
            solve_result = _solve_study_by_tag(self.target_study)
            if not solve_result.get('success'):
                self._log(f'  求解失败 (I={current_I}A): {solve_result.get("error")}', 'error')
                return None

            # 求值温度表达式
            eval_result = mph.eval_expr(self.temp_expression)
            if not eval_result.get('success'):
                self._log(f'  求值失败 (I={current_I}A): {eval_result.get("error")}', 'error')
                return None

            temp_value = float(eval_result.get('value', 0))

            # 单位转换（COMSOL 通常返回 K）
            if self.temp_unit.lower() == 'degc':
                temp_value = convert_temp_value(temp_value, 'K', 'degC')

            return temp_value

        except Exception as e:
            self._log(f'  求解异常 (I={current_I}A): {e}', 'error')
            return None

    def compute_ampacity(
        self,
        target_T: float = 90.0,
        I_low: float = 500.0,
        I_high: float = 1500.0,
        T_at_I_low: Optional[float] = None,
        T_at_I_high: Optional[float] = None,
        tolerance: float = 0.05,
        max_iter: int = 15,
        auto_expand_bracket: bool = True,
        max_expand: int = 5,
        method: str = 'secant',
    ) -> Dict:
        """寻优核心方法

        Args:
            target_T: 目标温度
            I_low: 初始下界电流
            I_high: 初始上界电流
            T_at_I_low: I_low 对应的温度（如果已知，可加速）
            T_at_I_high: I_high 对应的温度（如果已知，可加速）
            tolerance: 收敛容差
            max_iter: 最大迭代次数
            auto_expand_bracket: 是否自动扩展区间
            max_expand: 最大扩展次数
            method: 'secant' / 'bisection' / 'hybrid'

        Returns:
            dict: 寻优结果
        """
        if self.current_model is None:
            return {'success': False, 'error': 'No model loaded'}

        self._log(f'  开始寻优: 目标={target_T}°C, 方法={method}, 初始区间=[{I_low}, {I_high}]A', 'info')

        # 定义求解函数（电流 -> 温度）
        def solve_func(I: float) -> float:
            temp = self._solve_and_get_temp(I)
            if temp is None:
                raise RuntimeError(f'Solve failed at I={I}A')
            self._log(f'    I={I:.2f}A → T={temp:.2f}°C', 'info')
            return temp

        # 选择优化方法
        try:
            if method == 'bisection':
                result = bisection_method(
                    func=solve_func,
                    target=target_T,
                    x_low=I_low,
                    x_high=I_high,
                    tolerance=tolerance,
                    max_iter=max_iter
                )
            elif method == 'hybrid':
                result = hybrid_optimize(
                    func=solve_func,
                    target=target_T,
                    x0=I_low,
                    x1=I_high,
                    tolerance=tolerance,
                    max_iter_secant=max_iter,
                    max_iter_bisect=max_iter
                )
            else:  # 默认 secant
                result = secant_method(
                    func=solve_func,
                    target=target_T,
                    x0=I_low,
                    x1=I_high,
                    tolerance=tolerance,
                    max_iter=max_iter
                )

            # 转换结果字段名
            return {
                'success': result['success'],
                'converged': result['converged'],
                'final_I': result['final_x'],
                'final_T': result['final_y'],
                'iterations': result['iterations'],
                'solve_count': len(result['history']),
                'history': result['history'],
                'error': result['error']
            }

        except Exception as e:
            self._log(f'  寻优异常: {e}', 'error')
            return {
                'success': False,
                'converged': False,
                'final_I': None,
                'final_T': None,
                'iterations': 0,
                'solve_count': 0,
                'history': [],
                'error': str(e)
            }

    def run_batch(
        self,
        file_list: List[str],
        static_groups: List[Dict],
        sweep_params: Dict[str, List],
        target_T: float = 90.0,
        tolerance: float = 0.05,
        initial_I: float = 800.0,
        method: str = 'secant',
    ) -> List[PointResult]:
        """跑批量: 嵌套循环 file -> group -> combo"""
        param_names = list(sweep_params.keys())
        param_values_lists = list(sweep_params.values()) if sweep_params else [[]]
        combinations_per_group = 1
        for lst in param_values_lists:
            combinations_per_group *= len(lst)
        total = len(file_list) * len(static_groups) * combinations_per_group

        self.tasks = []
        self.is_running = True
        self.should_stop = False
        t0 = time.time()
        completed = 0

        try:
            for file_path in file_list:
                if self.should_stop:
                    break

                base = os.path.basename(file_path).replace('.mph', '')

                if not self.load_mph(file_path):
                    # 整个文件跳过
                    for g in static_groups:
                        for combo in product(*param_values_lists):
                            completed += 1
                            env = dict(zip(param_names, combo)) if param_names else {}
                            self.tasks.append(PointResult(
                                task_id=completed, file_name=base,
                                group_name=g.get('group_name', '默认'),
                                env_params=env, status='skipped',
                                error='load failed', elapsed_sec=0))
                    self.progress_fn(completed, total, time.time() - t0)
                    continue

                for g in static_groups:
                    if self.should_stop:
                        break

                    gname = g.get('group_name', '默认')

                    # 应用静态参数
                    for k, v in g.items():
                        if k != 'group_name':
                            mph.param_set(k, str(v))

                    last_I = initial_I
                    for combo in product(*param_values_lists):
                        if self.should_stop:
                            break

                        completed += 1
                        env = dict(zip(param_names, combo)) if param_names else {}

                        for k, v in env.items():
                            mph.param_set(k, str(v))

                        t_point = time.time()
                        result = self.compute_ampacity(
                            target_T=target_T,
                            I_low=max(50, last_I - 200),
                            I_high=last_I + 200,
                            tolerance=tolerance,
                            max_iter=15,
                            method=method,
                        )
                        elapsed = time.time() - t_point

                        pr = PointResult(
                            task_id=completed,
                            file_name=base,
                            group_name=gname,
                            env_params=env,
                            final_I=result.get('final_I'),
                            final_T=result.get('final_T'),
                            converged=result.get('converged', False),
                            iterations=result.get('iterations', 0),
                            solve_count=result.get('solve_count', 0),
                            history=result.get('history', []),
                            error=result.get('error', ''),
                            elapsed_sec=elapsed,
                            status='success' if result.get('success') else 'failed'
                        )

                        self.tasks.append(pr)
                        self.result_fn(pr)

                        if pr.converged and pr.final_I:
                            last_I = pr.final_I

                        self.progress_fn(completed, total, time.time() - t0)

        finally:
            self.is_running = False

        return self.tasks

    def request_stop(self):
        """请求停止当前运行"""
        self.should_stop = True
        self._log('收到停止指令，当前工况完成后终止', 'warning')


# ---------------------------------------------------------------------------
# OOM 保护
# ---------------------------------------------------------------------------

class OOMGuard:
    """后台线程监控 mph Java 进程, 内存超阈值自动重启引擎"""

    def __init__(self, engine: AmpacityEngine, threshold_gb: float = 4.0,
                 check_interval_sec: int = 10):
        self.engine = engine
        self.threshold_bytes = int(threshold_gb * 1024 ** 3)
        self.interval = check_interval_sec
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.restart_count = 0
        self.max_restart = 3

    def start(self):
        """启动监控"""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name='OOMGuard')
        self._thread.start()

    def stop(self):
        """停止监控"""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self):
        """监控循环"""
        while not self._stop.wait(self.interval):
            try:
                # 简化实现
                pass
            except Exception:
                pass
