import tempfile
import os

def load_with_temp(data: bytes, suffix: str, loader_fn):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, f"model{suffix}")

        with open(path, "wb") as f:
            f.write(data)

        model = loader_fn(path)

        return model



def load_temp_file(data: bytes, suffix: str):
    fd, path = tempfile.mkstemp(suffix=suffix)

    with os.fdopen(fd, "wb") as f:
        f.write(data)

    return path


def safe_load(path: str, loader):
    try:
        return loader(path)
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


import tempfile
import os

with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "model.onnx")
    with open(path, "wb") as f:
        f.write(data)
    return ort.InferenceSession(path)


sklearn
@ModelArtifact.register("sklearn")
def _sklearn(data: bytes):
    import joblib
    from io import BytesIO
    return joblib.load(BytesIO(data))
xgboost
@ModelArtifact.register("xgboost")
def _xgboost(data: bytes):
    import xgboost as xgb
    model = xgb.Booster()
    model.load_model(bytearray(data))
    return model
lightgbm
@ModelArtifact.register("lightgbm")
def _lightgbm(data: bytes):
    import lightgbm as lgb
    return lgb.Booster(model_str=data.decode("utf-8"))
torch
@ModelArtifact.register("torch")
def _torch(data: bytes):
    import torch
    from io import BytesIO
    return torch.load(BytesIO(data), map_location="cpu")
tensorflow（必须注意生命周期）
@ModelArtifact.register("tensorflow")
def _tensorflow(data: bytes):
    import tensorflow as tf
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "model.keras")
        with open(path, "wb") as f:
            f.write(data)
        return tf.keras.models.load_model(path)
onnx
@ModelArtifact.register("onnx")
def _onnx(data: bytes):
    import onnxruntime as ort
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "model.onnx")
        with open(path, "wb") as f:
            f.write(data)
        return ort.InferenceSession(path)
catboost
@ModelArtifact.register("catboost")
def _catboost(data: bytes):
    import catboost as cb
    import tempfile
    import os

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "model.cbm")
        with open(path, "wb") as f:
            f.write(data)

        model = cb.CatBoost()
        model.load_model(path)
        return model