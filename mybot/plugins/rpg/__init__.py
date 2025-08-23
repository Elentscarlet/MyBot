# mybot/plugins/rpg/__init__.py
# -*- coding: utf-8 -*-
"""
RPG 插件（包入口）：仅导入各功能模块以注册 matcher
"""
from .handlers import help  # noqa: F401
from .handlers import profile  # noqa: F401
from .handlers import rename  # noqa: F401
from .handlers import list_players  # noqa: F401
from .handlers import daily  # noqa: F401
from .handlers import gacha  # noqa: F401
from .handlers import refine  # noqa: F401
from .handlers import wild  # noqa: F401
from .handlers import pvp  # noqa: F401
from .handlers import boss  # noqa: F401
from .handlers import redistribute  # noqa: F401
