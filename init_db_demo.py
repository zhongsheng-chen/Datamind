from datamind.db.init import init_db
from datamind.config import get_settings


def main():
    settings = get_settings()

    # 初始化数据库（创建所有表）
    init_db(settings.database)



if __name__ == "__main__":
    main()