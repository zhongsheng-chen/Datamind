#!/usr/bin/env python3
# datamind/scripts/benchmark.py
"""
性能测试脚本
用于测试模型推理性能
"""

import sys
import time
import json
import random
import asyncio
import aiohttp
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import argparse
import logging
from concurrent.futures import ThreadPoolExecutor
import numpy as np

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from datamind.core.ml.model_loader import model_loader
from datamind.core.ml.inference import inference_engine
from datamind.core.ml.model_registry import model_registry
from datamind.config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Benchmark:
    """性能测试工具"""

    def __init__(self, model_id: str, concurrency: int = 10, requests: int = 100):
        self.model_id = model_id
        self.concurrency = concurrency
        self.total_requests = requests

        self.results = []
        self.errors = []

        # 加载测试数据
        self.test_data = self._load_test_data()

    def _load_test_data(self) -> List[Dict]:
        """加载测试数据"""
        # 获取模型信息
        model_info = model_registry.get_model_info(self.model_id)
        if not model_info:
            raise ValueError(f"模型不存在: {self.model_id}")

        # 生成随机测试数据
        test_data = []
        features = model_info['input_features']

        for _ in range(min(100, self.total_requests)):
            data = {}
            for f in features:
                # 根据特征名生成随机值
                if 'age' in f.lower():
                    data[f] = random.randint(18, 80)
                elif 'income' in f.lower():
                    data[f] = random.randint(20000, 200000)
                elif 'score' in f.lower():
                    data[f] = random.randint(300, 850)
                elif 'amount' in f.lower():
                    data[f] = random.randint(1000, 100000)
                else:
                    data[f] = random.random()
            test_data.append(data)

        return test_data

    def run_local_benchmark(self):
        """本地性能测试"""
        logger.info(f"开始本地性能测试: 并发={self.concurrency}, 请求数={self.total_requests}")

        # 确保模型已加载
        if not model_loader.is_loaded(self.model_id):
            model_loader.load_model(self.model_id, "benchmark")

        start_time = time.time()

        def make_request():
            try:
                data = random.choice(self.test_data)
                req_start = time.time()

                # 根据模型类型选择预测方法
                model_info = model_registry.get_model_info(self.model_id)
                if model_info['task_type'] == 'scoring':
                    result = inference_engine.predict_scorecard(
                        model_id=self.model_id,
                        features=data,
                        application_id=f"benchmark_{int(time.time())}",
                        user_id="benchmark"
                    )
                else:
                    result = inference_engine.predict_fraud(
                        model_id=self.model_id,
                        features=data,
                        application_id=f"benchmark_{int(time.time())}",
                        user_id="benchmark"
                    )

                req_time = (time.time() - req_start) * 1000

                self.results.append({
                    'success': True,
                    'time': req_time,
                    'result': result
                })

            except Exception as e:
                req_time = (time.time() - req_start) * 1000
                self.errors.append({
                    'success': False,
                    'time': req_time,
                    'error': str(e)
                })

        # 使用线程池并发执行
        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            futures = []
            for _ in range(self.total_requests):
                futures.append(executor.submit(make_request))

            # 等待所有完成
            for f in futures:
                f.result()

        total_time = time.time() - start_time

        self._print_results(total_time)

    async def run_http_benchmark(self, url: str, api_key: str):
        """HTTP API性能测试"""
        logger.info(f"开始HTTP性能测试: {url}")

        connector = aiohttp.TCPConnector(limit=self.concurrency)
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = []
            for i in range(self.total_requests):
                tasks.append(self._make_http_request(session, url, api_key))

            await asyncio.gather(*tasks)

    async def _make_http_request(self, session, url: str, api_key: str):
        """执行HTTP请求"""
        try:
            data = random.choice(self.test_data)

            headers = {
                'X-API-Key': api_key,
                'Content-Type': 'application/json'
            }

            payload = {
                'application_id': f"benchmark_{int(time.time())}",
                'features': data
            }

            start_time = time.time()

            async with session.post(url, json=payload, headers=headers) as response:
                result = await response.json()
                req_time = (time.time() - start_time) * 1000

                self.results.append({
                    'success': response.status == 200,
                    'time': req_time,
                    'status': response.status,
                    'result': result
                })

        except Exception as e:
            req_time = (time.time() - start_time) * 1000
            self.errors.append({
                'success': False,
                'time': req_time,
                'error': str(e)
            })

    def _print_results(self, total_time: float):
        """打印测试结果"""
        if not self.results:
            logger.warning("没有成功的结果")
            return

        times = [r['time'] for r in self.results]

        print("\n" + "=" * 60)
        print("性能测试结果")
        print("=" * 60)
        print(f"总请求数: {self.total_requests}")
        print(f"成功数: {len(self.results)}")
        print(f"失败数: {len(self.errors)}")
        print(f"总耗时: {total_time:.2f} 秒")
        print(f"吞吐量: {self.total_requests / total_time:.2f} 请求/秒")
        print("\n响应时间统计 (ms):")
        print(f"  平均: {np.mean(times):.2f}")
        print(f"  中位数: {np.median(times):.2f}")
        print(f"  最小: {np.min(times):.2f}")
        print(f"  最大: {np.max(times):.2f}")
        print(f"  P95: {np.percentile(times, 95):.2f}")
        print(f"  P99: {np.percentile(times, 99):.2f}")
        print(f"  标准差: {np.std(times):.2f}")

        # 保存结果
        self._save_results()

    def _save_results(self):
        """保存测试结果"""
        output_dir = Path("benchmark_results")
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存详细结果
        result_file = output_dir / f"benchmark_{timestamp}.json"
        with open(result_file, 'w') as f:
            json.dump({
                'summary': {
                    'total': self.total_requests,
                    'success': len(self.results),
                    'errors': len(self.errors),
                    'avg_time': np.mean([r['time'] for r in self.results]),
                    'p95': np.percentile([r['time'] for r in self.results], 95)
                },
                'results': self.results,
                'errors': self.errors
            }, f, indent=2, default=str)

        logger.info(f"结果已保存到: {result_file}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="性能测试工具")
    parser.add_argument("model_id", help="要测试的模型ID")
    parser.add_argument("--concurrency", type=int, default=10,
                        help="并发数")
    parser.add_argument("--requests", type=int, default=100,
                        help="总请求数")
    parser.add_argument("--mode", choices=["local", "http"], default="local",
                        help="测试模式")
    parser.add_argument("--url", help="HTTP API URL")
    parser.add_argument("--api-key", default="demo-key",
                        help="API密钥")

    args = parser.parse_args()

    benchmark = Benchmark(
        model_id=args.model_id,
        concurrency=args.concurrency,
        requests=args.requests
    )

    if args.mode == "local":
        benchmark.run_local_benchmark()
    else:
        if not args.url:
            args.url = f"http://localhost:{settings.API_PORT}{settings.API_PREFIX}"
            if args.model_id.startswith('MDL_'):
                # 根据模型类型选择端点
                model_info = model_registry.get_model_info(args.model_id)
                if model_info['task_type'] == 'scoring':
                    args.url += f"/scoring/predict?model_id={args.model_id}"
                else:
                    args.url += f"/fraud/predict?model_id={args.model_id}"

        asyncio.run(benchmark.run_http_benchmark(args.url, args.api_key))
        benchmark._print_results(0)


if __name__ == "__main__":
    main()