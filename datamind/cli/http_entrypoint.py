"""HTTP 服务子进程入口：保留 BentoML 日志，由父启动入口提示停止方式."""

import logging
import runpy


class StartupHintFilter(logging.Filter):
    """只去掉 BentoML 启动日志附带的停止提示，不屏蔽日志或异常."""

    def filter(self, record: logging.LogRecord) -> bool:
        """保留启动信息及严重程度，将交互提示留给父进程."""
        suffix = " (Press CTRL+C to quit)"
        if (
                record.name == "bentoml.serve"
                and isinstance(record.msg, str)
                and record.msg.startswith("Starting production ")
                and record.msg.endswith(suffix)
        ):
            record.msg = record.msg.removesuffix(suffix)
        return True


def main() -> None:
    """调用原 BentoML CLI，不改变参数、信号处理或退出行为."""
    logging.getLogger("bentoml.serve").addFilter(StartupHintFilter())
    runpy.run_module("bentoml", run_name="__main__")


if __name__ == "__main__":
    main()
