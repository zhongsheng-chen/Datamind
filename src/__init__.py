import os

# 禁用 OneDNN 优化
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"