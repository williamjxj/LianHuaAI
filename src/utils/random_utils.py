"""随机选择工具"""

import random
from typing import Dict, List, Optional, TypeVar

T = TypeVar("T")


def weighted_choice(items: Dict[T, float]) -> T:
    """按权重随机选择

    Args:
        items: {选项: 权重} 映射

    Returns:
        按权重选中的选项
    """
    choices, weights = zip(*items.items())
    return random.choices(choices, weights=weights, k=1)[0]


def pick_random[T](items: List[T], exclude: Optional[List[T]] = None) -> T:
    """从列表中随机选取，可排除部分选项

    Args:
        items: 候选列表
        exclude: 需排除的项

    Returns:
        随机选中的项
    """
    pool = list(items)
    if exclude:
        pool = [x for x in pool if x not in exclude]
    return random.choice(pool)
