import os

# 禁用 OneDNN 优化
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

# 抑制 TENSORFLOW 和 SQLALCHEMY 警告
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
os.environ["SQLALCHEMY_SILENCE_UBER_WARNING"] = "1"
