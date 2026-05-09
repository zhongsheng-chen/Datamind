# Datamind/datamind/cli/utils/progress.py

"""进度指示工具

提供命令行界面的进度显示功能，包括进度条和旋转指示器。

功能特性：
  - 进度条管理器（ProgressBar）：显示百分比进度、耗时、状态信息
  - 旋转指示器（spinner）：用于不确定时长的操作
  - 上下文管理器支持（with 语句自动处理开始和结束）

使用场景：
  - 文件上传/下载：显示上传/下载进度
  - 模型训练：显示训练进度和耗时
  - 数据处理：显示处理进度
  - 网络请求：显示等待状态（使用 spinner）

使用示例：
  # 使用进度条（自动管理）
  with ProgressBar("加载模型", "模型加载完成") as pb:
      pb.update(30, "验证模型...")
      time.sleep(1)
      pb.update(70, "加载权重...")
      time.sleep(1)
      pb.update(100, "完成")

  # 使用旋转指示器
  with spinner("加载模型"):
      time.sleep(3)  # 模拟耗时操作

进度条效果：
  加载模型...
    ████████████████████████████████████████ 100% 2.5s [完成]
  ✅ 模型加载完成 (耗时: 2.5s)

旋转指示器效果：
  ⠋ 加载模型...
  ✅ 加载模型完成
"""

import click
import time
from contextlib import contextmanager


class ProgressBar:
    """进度条管理器

    提供命令行进度条显示功能，支持：
      - 百分比进度显示
      - 耗时计时
      - 状态信息显示
      - 上下文管理器自动管理生命周期

    使用示例：
        with ProgressBar("加载模型", "模型加载完成") as pb:
            pb.update(30, "验证模型...")
            pb.update(70, "加载权重...")
            pb.update(100, "完成")
    """

    def __init__(self, description: str = "处理中", complete_message: str = "完成"):
        """
        初始化进度条

        参数:
            description: 进度条描述文本
            complete_message: 完成时显示的消息
        """
        self.description = description
        self.complete_message = complete_message
        self.current = 0
        self.total = 100
        self.start_time = None

    def __enter__(self):
        """进入上下文，开始进度条"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文，结束进度条

        如果发生异常，不显示完成信息，只换行
        """
        if exc_type is None:
            self.finish()
        else:
            click.echo()

    def start(self):
        """开始进度条

        记录开始时间，显示描述信息，并渲染初始进度条
        """
        self.start_time = time.time()
        click.echo(f"\n{self.description}...")
        self._render()

    def update(self, progress: int, status: str = None):
        """
        更新进度

        参数:
            progress: 进度值 (0-100)
            status: 状态信息，显示在进度条右侧
        """
        self.current = min(progress, 100)
        self._render(status)

    def _render(self, status: str = None):
        """渲染进度条

        参数:
            status: 状态信息
        """
        bar_length = 40
        filled_length = int(bar_length * self.current / 100)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)

        elapsed = time.time() - self.start_time if self.start_time else 0
        elapsed_str = f"{elapsed:.1f}s"

        status_text = f" [{status}]" if status else ""
        click.echo(
            f"\r  {bar} {self.current:3d}% {elapsed_str}{status_text}",
            nl=False
        )

    def finish(self):
        """完成进度条

        显示完成消息和总耗时
        """
        elapsed = time.time() - self.start_time if self.start_time else 0
        click.echo(f"\n✅ {self.complete_message} (耗时: {elapsed:.1f}s)")


@contextmanager
def spinner(description: str = "处理中"):
    """
    旋转指示器上下文管理器

    用于不确定时长的操作，显示一个不断旋转的动画。

    参数:
        description: 描述信息

    使用示例：
        with spinner("加载模型"):
            time.sleep(3)  # 模拟耗时操作

    注意：
        - 使用独立线程显示动画，不会阻塞主线程
        - 自动处理线程清理，退出上下文后停止动画
        - 适用于网络请求、数据库查询等不确定时长的操作
    """
    import itertools
    import threading

    stop_spinner = threading.Event()

    def spin():
        """旋转动画线程函数"""
        for char in itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧']):
            if stop_spinner.is_set():
                break
            click.echo(f"\r{char} {description}...", nl=False)
            time.sleep(0.1)
        # 清除最后一行的内容
        click.echo("\r" + " " * (len(description) + 10), nl=False)

    # 启动旋转动画线程
    spinner_thread = threading.Thread(target=spin)
    spinner_thread.start()

    try:
        yield
    finally:
        # 停止动画并等待线程结束
        stop_spinner.set()
        spinner_thread.join()
        # 显示完成信息
        click.echo(f"\r✅ {description}完成")