from setuptools import setup, find_packages

setup(
    name="datamind",
    version="1.0.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        # 依赖列表
    ],
    entry_points={
        'console_scripts': [
            'datamind=cli.main:cli',
        ],
    },
    author="Datamind Team",
    description="金融级模型部署平台",
    classifiers=[
        'Programming Language :: Python :: 3.9',
        'Operating System :: OS Independent',
    ],
)