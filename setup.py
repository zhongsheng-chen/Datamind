# datamind/setup.py
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="datamind",
    version="0.1.0",
    author="Zhongsheng Chen",
    description="Datamind 模型部署平台",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/datamind",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "click>=8.0.0",
        "requests>=2.25.0",
        "pyyaml>=5.4.0",
    ],
    entry_points={
        "console_scripts": [
            "datamind=cli.main:main",
        ],
    },
    include_package_data=True,
)