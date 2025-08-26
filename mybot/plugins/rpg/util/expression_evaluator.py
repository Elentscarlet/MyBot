import random
import math
from typing import Dict, Any


class ExpressionEvaluator:
    def __init__(self):
        self.safe_globals = {
            'min': min,
            'max': max,
            'abs': abs,
            'round': round,
            'int': int,
            'float': float,
            'random': random.random,
            'randint': random.randint,
            'math': math,
            'len': len,
            'sum': sum
        }

    def evaluate(self, expr: str, context: Dict[str, Any]) -> Any:
        """安全地求值表达式"""
        if not expr or not isinstance(expr, str):
            return None

        try:
            # 创建安全的求值环境
            safe_locals = context.copy()
            safe_locals.update(self.safe_globals)

            # 添加单位属性访问
            # self._inject_unit_attributes(safe_locals, context)

            return eval(expr, {'__builtins__': {}}, safe_locals)
        except Exception as e:
            print(f"表达式求值错误: {expr}, 错误: {e}")
            return None

    def _inject_unit_attributes(self, context: Dict, original_context: Dict):
        """注入单位属性到上下文"""
        for key in ['source', 'target', 'attacker', 'defender']:
            if key in original_context:
                unit = original_context[key]
                if hasattr(unit, '__dict__'):
                    # 添加带前缀的属性
                    for attr_name, attr_value in unit.__dict__.items():
                        if not attr_name.startswith('_'):
                            context[f"{key}.{attr_name}"] = attr_value