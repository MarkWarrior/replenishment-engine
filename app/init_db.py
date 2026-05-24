"""
数据库初始化 + 示例数据
运行：python -m app.init_db
"""

from app.models.database import get_engine, create_tables, get_session, init_sample_data

def main():
    print("初始化数据库...")
    engine = get_engine("replenishment.db")
    create_tables(engine)
    print("✅ 表创建成功")

    session = get_session(engine)
    try:
        # 检查是否已有数据
        from app.models.database import SKU
        existing = session.query(SKU).first()
        if not existing:
            init_sample_data(session)
            print("✅ 示例数据已初始化")
        else:
            print("ℹ️ 数据已存在，跳过示例数据")
    finally:
        session.close()


if __name__ == "__main__":
    main()