# datamind/console/assets.py

"""管理控制台静态资源

为构建产物提供静态文件响应，并按文件类型设置浏览器缓存策略。

核心功能：
  - ConsoleStaticFiles: 提供控制台静态资源
"""

import re
from pathlib import Path

from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class ConsoleStaticFiles(StaticFiles):
    """管理控制台静态资源服务"""

    async def get_response(self, path: str, scope: Scope) -> Response:
        """返回静态资源响应

        参数：
            path: 相对资源路径
            scope: ASGI 请求上下文

        返回：
            带缓存策略的静态资源响应
        """
        response = await super().get_response(path, scope)
        fingerprinted = re.fullmatch(
            r".+-[A-Za-z0-9_-]{8,}\.[A-Za-z0-9]+",
            Path(path).name,
        )
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable"
            if fingerprinted and response.status_code in {200, 206, 304}
            else "no-cache"
        )
        return response
