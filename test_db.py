# 测试数据库连接
from monitor.database import db_manager

print('数据库连接测试:')
try:
    with db_manager.get_session() as session:
        result = session.execute('SELECT 1').scalar()
        print(f'连接成功: {result}')
except Exception as e:
    print(f'连接失败: {e}')

print('\nRedis连接测试:')
try:
    redis = db_manager.get_redis()
    if redis:
        result = redis.ping()
        print(f'连接成功: {result}')
    else:
        print('Redis客户端未初始化')
except Exception as e:
    print(f'连接失败: {e}')