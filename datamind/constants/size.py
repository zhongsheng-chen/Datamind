# datamind/constants/size.py

"""存储大小常量

定义常用的存储单位换算，用于配置文件和内存计算。

核心功能：
  - KB: 千字节（1024字节）
  - MB: 兆字节（1024 * 1024字节）
  - GB: 吉字节（1024 * 1024 * 1024字节）

使用示例：
  from datamind.constants.size import MB

  # 配置 200MB 文件大小限制
  max_file_size: int = 200 * MB
"""

KB: int = 1024
MB: int = 1024 * KB
GB: int = 1024 * MB