from datamind.storage import get_storage
from datamind.config import get_settings
from datamind.logging import setup_logging, get_logger, request_context


def main():
    settings = get_settings()
    setup_logging(settings.logging)

    storage = get_storage()
    logger = get_logger(__name__)

    model_id = "m1"
    filename = "model.pkl"

    # =========================
    # 加入请求级上下文
    # =========================
    with request_context(trace_id="trace-001", request_id="req-001"):

        # =========================
        # 1. 写入模型文件
        # =========================
        data = b"this is a fake model binary"

        print("=== SAVE ===")
        storage.save(model_id, filename, data)
        logger.info("save completed", model_id=model_id, filename=filename)

        print("saved:", model_id, filename)

        # =========================
        # 2. 判断是否存在
        # =========================
        print("\n=== EXISTS ===")
        exists = storage.exists(model_id, filename)
        logger.info("exists checked", exists=exists)

        print("exists:", exists)

        # =========================
        # 3. 读取模型文件
        # =========================
        print("\n=== LOAD ===")
        loaded = storage.load(model_id, filename)
        logger.info("load completed", size=len(loaded))

        print("loaded:", loaded)

        # =========================
        # 4. 删除模型文件
        # =========================
        print("\n=== DELETE ===")
        storage.delete(model_id, filename)
        logger.info("delete completed")

        print("deleted:", model_id, filename)

        # =========================
        # 5. 再检查是否存在
        # =========================
        print("\n=== EXISTS AFTER DELETE ===")
        exists_after = storage.exists(model_id, filename)
        logger.info("exists after delete", exists=exists_after)

        print("exists:", exists_after)


if __name__ == "__main__":
    main()