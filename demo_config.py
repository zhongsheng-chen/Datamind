# run_config_demo.py

from datamind.config.settings import get_settings


def main():
    # 获取配置
    settings = get_settings()

    print("\n========== DATAMIND CONFIG DEMO ==========\n")

    # Scorecard
    print("[Scorecard]")
    print("base_score :", settings.scorecard.base_score)
    print("base_odds  :", settings.scorecard.base_odds)
    print("pdo        :", settings.scorecard.pdo)
    print("min_score  :", settings.scorecard.min_score)
    print("max_score  :", settings.scorecard.max_score)

    print("\n------------------------------------------\n")

    # Storage
    print("[Storage]")
    print("backend    :", settings.storage.backend)
    print("endpoint   :", getattr(settings.storage, "endpoint", None))
    print("bucket     :", getattr(settings.storage, "bucket", None))

    print("\n------------------------------------------\n")

    # Logging
    print("[Logging]")
    print("level      :", settings.logging.level)
    print("format     :", settings.logging.format)

    print("\n==========================================\n")


if __name__ == "__main__":
    main()