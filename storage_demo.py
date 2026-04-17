from datamind.storage import get_storage


def main():
    # 获取唯一存储实例（lru_cache 单例）
    storage = get_storage()

    model_id = "m1"
    filename = "model.pkl"

    # =========================
    # 1. 写入模型文件
    # =========================
    data = b"this is a fake model binary"

    print("=== SAVE ===")
    storage.save(model_id, filename, data)
    print("saved:", model_id, filename)

    # =========================
    # 2. 判断是否存在
    # =========================
    print("\n=== EXISTS ===")
    exists = storage.exists(model_id, filename)
    print("exists:", exists)

    # =========================
    # 3. 读取模型文件
    # =========================
    print("\n=== LOAD ===")
    loaded = storage.load(model_id, filename)
    print("loaded:", loaded)

    # =========================
    # 4. 删除模型文件
    # =========================
    print("\n=== DELETE ===")
    storage.delete(model_id, filename)
    print("deleted:", model_id, filename)

    # =========================
    # 5. 再检查是否存在
    # =========================
    print("\n=== EXISTS AFTER DELETE ===")
    print("exists:", storage.exists(model_id, filename))


if __name__ == "__main__":
    main()