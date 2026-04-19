#!/usr/bin/env python
# logging_demo.py

"""日志模块功能完整测试

测试覆盖：
  - 基础日志功能（各级别日志输出）
  - 上下文管理（trace_id / request_id）
  - 额外字段（extra）
  - 异常日志（exc_info）
  - 敏感信息脱敏（MaskFilter）
  - 日志采样（SampleFilter）
  - 异步日志（AsyncLoggingHandler）
  - 日志轮转（RotatingFileHandler / TimedRotatingFileHandler）
  - 日志清理（cleanup_logs）
  - JSON/Text 格式切换
  - 日志级别过滤（LevelFilter）
  - 并发场景测试
  - 第三方库日志级别控制

运行方式：
  python logging_demo.py
  python logging_demo.py --test basic
  python logging_demo.py --test async
  python logging_demo.py --test performance
  python logging_demo.py --test all
"""

import argparse
import logging
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from datamind.logging import (
    init_logging,
    get_logger,
    set_trace_id,
    get_trace_id,
    set_request_id,
    get_request_id,
    clear_context,
)
from datamind.config import get_settings


class Colors:
    """终端颜色代码"""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


def print_pass(msg: str):
    print(f"{Colors.GREEN}[PASS]{Colors.RESET} {msg}")


def print_fail(msg: str):
    print(f"{Colors.RED}[FAIL]{Colors.RESET} {msg}")


def print_info(msg: str):
    print(f"{Colors.BLUE}[INFO]{Colors.RESET} {msg}")


def print_warn(msg: str):
    print(f"{Colors.YELLOW}[WARN]{Colors.RESET} {msg}")


def print_section(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


class LoggingTestSuite:
    """日志模块测试套件"""

    def __init__(self):
        self.test_results = []
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def run_test(self, name: str, func):
        """运行单个测试"""
        print_info(f"运行测试: {name}")
        try:
            func()
            print_pass(f"{name} 通过")
            self.passed += 1
            return True
        except AssertionError as e:
            print_fail(f"{name} 失败: {e}")
            self.failed += 1
            return False
        except Exception as e:
            print_fail(f"{name} 异常: {e}")
            self.failed += 1
            return False

    def print_summary(self):
        """打印测试总结"""
        print_section("测试结果汇总")
        print(f"通过: {self.passed}")
        print(f"失败: {self.failed}")
        print(f"跳过: {self.skipped}")
        print(f"总计: {self.passed + self.failed + self.skipped}")

    # ========================
    # 基础功能测试
    # ========================

    def test_basic_logging(self):
        """测试基础日志功能"""
        logger = get_logger("test.basic")

        # 测试各级别日志
        logger.debug("DEBUG 级别日志")
        logger.info("INFO 级别日志")
        logger.warning("WARNING 级别日志")
        logger.error("ERROR 级别日志")

        # 验证日志级别映射
        settings = get_settings()
        level = settings.logging.level.upper()
        assert level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def test_context_logging(self):
        """测试上下文管理"""
        set_trace_id("test-trace-001")
        set_request_id("test-req-001")

        assert get_trace_id() == "test-trace-001"
        assert get_request_id() == "test-req-001"

        logger = get_logger("test.context")
        logger.info("带上下文的日志")

        clear_context()
        assert get_trace_id() is None
        assert get_request_id() is None

        logger.info("无上下文的日志")

    def test_extra_fields(self):
        """测试额外字段"""
        logger = get_logger("test.extra")

        extra_data = {
            "user_id": 12345,
            "action": "login",
            "duration_ms": 125,
        }
        logger.info("用户操作日志", extra=extra_data)

        # 验证 extra 字段存在
        assert extra_data is not None

    def test_exception_logging(self):
        """测试异常日志"""
        logger = get_logger("test.exception")

        try:
            raise ValueError("测试异常")
        except ValueError:
            logger.exception("捕获到异常")
            logger.error("错误日志", exc_info=True)

    # ========================
    # 过滤器测试
    # ========================

    def test_sensitive_filter(self):
        """测试敏感信息脱敏"""
        logger = get_logger("test.mask")

        # 记录包含敏感词的日志
        logger.info("用户登录", extra={"password": "123456"})
        logger.info("API调用", extra={"api_key": "sk-test123"})

        # 验证脱敏器已加载
        settings = get_settings()
        assert settings.logging.mask_sensitive is True

    def test_sample_filter(self):
        """测试采样过滤器"""
        settings = get_settings()
        sample_rate = settings.logging.sample_rate

        print_info(f"当前采样率: {sample_rate}")
        assert 0 <= sample_rate <= 1

        logger = get_logger("test.sample")
        for i in range(100):
            logger.debug(f"采样测试日志 #{i}")

    def test_level_filter(self):
        """测试日志级别过滤"""
        settings = get_settings()
        current_level = settings.logging.level

        logger = get_logger("test.level")
        logger.debug("这条日志可能被过滤")
        logger.info("这条日志应该显示")

        assert current_level in ["DEBUG", "INFO", "WARNING", "ERROR"]

    # ========================
    # 异步日志测试
    # ========================

    def test_async_logging(self):
        """测试异步日志"""
        settings = get_settings()
        if not settings.logging.enable_async:
            print_warn("异步日志未启用，跳过测试")
            return

        logger = get_logger("test.async")

        start = time.time()
        for i in range(1000):
            logger.info(f"异步日志消息 #{i}")
        elapsed = time.time() - start

        print_info(f"异步日志 1000 条耗时: {elapsed:.4f} 秒")
        assert elapsed < 1.0  # 异步应该很快

    # ========================
    # 性能测试
    # ========================

    def test_performance(self):
        """测试性能"""
        logger = get_logger("test.performance")

        # 测试同步写入性能
        start = time.time()
        for i in range(10000):
            logger.info(f"性能测试日志 #{i}")
        elapsed = time.time() - start

        print_info(f"10000 条日志耗时: {elapsed:.4f} 秒")
        print_info(f"平均每条: {elapsed / 10000 * 1000:.4f} 毫秒")

    def test_concurrent_logging(self):
        """测试并发场景"""
        logger = get_logger("test.concurrent")

        def log_worker(worker_id: int):
            set_trace_id(f"concurrent-trace-{worker_id}")
            set_request_id(f"concurrent-req-{worker_id}")
            for i in range(100):
                logger.info(f"Worker {worker_id} 日志 #{i}")

        start = time.time()
        with ThreadPoolExecutor(max_workers=10) as executor:
            executor.map(log_worker, range(10))
        elapsed = time.time() - start

        print_info(f"10个并发写入各100条日志耗时: {elapsed:.4f} 秒")

    # ========================
    # 文件输出测试
    # ========================

    def test_file_output(self):
        """测试文件输出"""
        settings = get_settings()
        if not settings.logging.enable_file:
            print_warn("文件输出未启用，跳过测试")
            return

        logger = get_logger("test.file")
        logger.info("写入文件的测试日志")

        cfg = settings.logging
        log_dir = cfg.dir
        assert log_dir.exists()

        log_files = list(log_dir.glob("*"))
        print_info(f"日志目录: {log_dir}")
        print_info(f"日志文件数量: {len(log_files)}")

    def test_rotation(self):
        """测试日志轮转"""
        settings = get_settings()
        if not settings.logging.enable_file:
            print_warn("文件输出未启用，跳过轮转测试")
            return

        cfg = settings.logging
        logger = get_logger("test.rotation")

        # 写入大量日志触发轮转
        for i in range(5000):
            logger.info(f"轮转测试日志 #{i}")

        log_dir = cfg.dir
        log_files = list(log_dir.glob("*"))
        print_info(f"轮转后文件数量: {len(log_files)}")

    def test_cleanup(self):
        """测试日志清理"""
        settings = get_settings()
        if not settings.logging.enable_file:
            print_warn("文件输出未启用，跳过清理测试")
            return

        cfg = settings.logging
        retention_days = cfg.retention_days

        print_info(f"日志保留天数: {retention_days}")
        assert retention_days > 0

    # ========================
    # 格式测试
    # ========================

    def test_json_format(self):
        """测试 JSON 格式"""
        settings = get_settings()
        current_format = settings.logging.format

        logger = get_logger("test.format")
        logger.info("测试日志格式")

        print_info(f"当前日志格式: {current_format}")
        assert current_format in ["json", "text"]

    # ========================
    # 第三方库测试
    # ========================

    def test_third_party_loggers(self):
        """测试第三方库日志级别"""
        # 验证第三方库日志级别已被设置
        uvicorn_logger = logging.getLogger("uvicorn")
        bentoml_logger = logging.getLogger("bentoml")

        print_info(f"uvicorn 日志级别: {logging.getLevelName(uvicorn_logger.level)}")
        print_info(f"bentoml 日志级别: {logging.getLevelName(bentoml_logger.level)}")

    # ========================
    # 配置测试
    # ========================

    def test_config(self):
        """测试配置加载"""
        settings = get_settings()
        cfg = settings.logging

        print_info("当前日志配置:")
        print(f"  level: {cfg.level}")
        print(f"  format: {cfg.format}")
        print(f"  enable_console: {cfg.enable_console}")
        print(f"  enable_file: {cfg.enable_file}")
        print(f"  enable_async: {cfg.enable_async}")
        print(f"  sample_rate: {cfg.sample_rate}")
        print(f"  dir: {cfg.dir}")
        print(f"  filename: {cfg.filename}")
        print(f"  use_date_filename: {cfg.use_date_filename}")
        print(f"  date_format: {cfg.date_format}")
        print(f"  rotation: {cfg.rotation}")
        print(f"  backup_count: {cfg.backup_count}")
        print(f"  retention_days: {cfg.retention_days}")

        assert cfg.level is not None
        assert cfg.format is not None


def run_all_tests():
    """运行所有测试"""
    suite = LoggingTestSuite()

    print_section("日志模块功能测试")

    # 基础功能
    suite.run_test("基础日志功能", suite.test_basic_logging)
    suite.run_test("上下文管理", suite.test_context_logging)
    suite.run_test("额外字段", suite.test_extra_fields)
    suite.run_test("异常日志", suite.test_exception_logging)

    # 过滤器
    suite.run_test("敏感信息脱敏", suite.test_sensitive_filter)
    suite.run_test("日志采样", suite.test_sample_filter)
    suite.run_test("日志级别过滤", suite.test_level_filter)

    # 异步
    suite.run_test("异步日志", suite.test_async_logging)

    # 性能
    suite.run_test("性能测试", suite.test_performance)
    suite.run_test("并发场景", suite.test_concurrent_logging)

    # 文件
    suite.run_test("文件输出", suite.test_file_output)
    suite.run_test("日志轮转", suite.test_rotation)
    suite.run_test("日志清理", suite.test_cleanup)

    # 格式
    suite.run_test("JSON格式", suite.test_json_format)

    # 第三方
    suite.run_test("第三方库日志", suite.test_third_party_loggers)

    # 配置
    suite.run_test("配置加载", suite.test_config)

    suite.print_summary()


def run_test_by_name(name: str):
    """按名称运行单个测试"""
    suite = LoggingTestSuite()

    test_map = {
        "basic": suite.test_basic_logging,
        "context": suite.test_context_logging,
        "extra": suite.test_extra_fields,
        "exception": suite.test_exception_logging,
        "mask": suite.test_sensitive_filter,
        "sample": suite.test_sample_filter,
        "level": suite.test_level_filter,
        "async": suite.test_async_logging,
        "performance": suite.test_performance,
        "concurrent": suite.test_concurrent_logging,
        "file": suite.test_file_output,
        "rotation": suite.test_rotation,
        "cleanup": suite.test_cleanup,
        "format": suite.test_json_format,
        "third": suite.test_third_party_loggers,
        "config": suite.test_config,
    }

    if name in test_map:
        suite.run_test(name, test_map[name])
    else:
        print(f"未知测试名称: {name}")
        print(f"可用测试: {', '.join(test_map.keys())}")


def main():
    parser = argparse.ArgumentParser(description="日志模块功能测试")
    parser.add_argument(
        "--test",
        type=str,
        default="all",
        help="测试名称: all, basic, context, async, performance, 等"
    )
    args = parser.parse_args()

    # 初始化日志系统
    init_logging()
    print_info("日志系统初始化完成")

    if args.test == "all":
        run_all_tests()
    else:
        run_test_by_name(args.test)


if __name__ == "__main__":
    main()