# datamind/cli/utils/progress.py
import click
import time
from contextlib import contextmanager


class ProgressBar:
    """进度条管理器"""

    def __init__(self, description: str = "处理中", complete_message: str = "完成"):
        self.description = description
        self.complete_message = complete_message
        self.current = 0
        self.total = 100
        self.start_time = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.finish()
        else:
            click.echo()

    def start(self):
        """开始进度条"""
        self.start_time = time.time()
        click.echo(f"\n{self.description}...")
        self._render()

    def update(self, progress: int, status: str = None):
        """
        更新进度

        Args:
            progress: 进度值 (0-100)
            status: 状态信息
        """
        self.current = min(progress, 100)
        self._render(status)

    def _render(self, status: str = None):
        """渲染进度条"""
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
        """完成进度条"""
        elapsed = time.time() - self.start_time if self.start_time else 0
        click.echo(f"\n✅ {self.complete_message} (耗时: {elapsed:.1f}s)")


@contextmanager
def spinner(description: str = "处理中"):
    """
    旋转指示器上下文管理器

    Args:
        description: 描述信息
    """
    import itertools
    import threading

    stop_spinner = threading.Event()

    def spin():
        for char in itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧']):
            if stop_spinner.is_set():
                break
            click.echo(f"\r{char} {description}...", nl=False)
            time.sleep(0.1)
        click.echo("\r" + " " * (len(description) + 10), nl=False)

    spinner_thread = threading.Thread(target=spin)
    spinner_thread.start()

    try:
        yield
    finally:
        stop_spinner.set()
        spinner_thread.join()
        click.echo(f"\r✅ {description}完成")