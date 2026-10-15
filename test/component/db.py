#!/usr/bin/env python3
"""
测试脚本 - 验证 ComponentMonitor 中数据库监测方法的逻辑
测试内容：
1. 驱动按需导入机制
2. 密码加密/解密
3. MySQL/PostgreSQL/DM/SQL Server 检测方法存在性
4. 分发逻辑正确性
5. 驱动缺失时的降级处理
"""

import asyncio
import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("ComponentMonitor 数据库监测功能测试")
print("=" * 60)

# 测试1: 驱动按需导入
print("\n[测试1] 驱动按需导入机制")
try:
    from monitors.component import _DB_DRIVERS, DB_DEFAULT_PORTS
    print(f"  已加载的驱动: {list(_DB_DRIVERS.keys())}")
    print(f"  默认端口配置: {DB_DEFAULT_PORTS}")
    assert 'mysql' in DB_DEFAULT_PORTS
    assert 'postgresql' in DB_DEFAULT_PORTS
    assert 'dm' in DB_DEFAULT_PORTS
    assert 'sqlserver' in DB_DEFAULT_PORTS
    assert DB_DEFAULT_PORTS['mysql'] == 3306
    assert DB_DEFAULT_PORTS['postgresql'] == 5432
    assert DB_DEFAULT_PORTS['dm'] == 5236
    assert DB_DEFAULT_PORTS['sqlserver'] == 1433
    print("  ✓ 驱动导入和默认端口配置正确")
except Exception as e:
    print(f"  ✗ 测试失败: {e}")
    sys.exit(1)

# 测试2: 密码加密/解密
print("\n[测试2] 密码加密/解密")
try:
    from monitors.component import _encrypt_password, _decrypt_password
    
    # 测试空密码
    assert _encrypt_password('') == ''
    assert _decrypt_password('') == ''
    print("  ✓ 空密码处理正确")
    
    # 测试明文密码（向后兼容）
    plain = "my_password"
    decrypted = _decrypt_password(plain)
    assert decrypted == plain
    print("  ✓ 明文密码向后兼容正确")
    
    # 测试加密/解密循环
    encrypted = _encrypt_password(plain)
    if encrypted.startswith('enc:'):
        decrypted = _decrypt_password(encrypted)
        assert decrypted == plain
        print("  ✓ 加密/解密循环正确（cryptography库可用）")
    else:
        # cryptography 库未安装，回退到明文
        assert encrypted == plain
        print("  ✓ 加密回退到明文（cryptography库未安装）")
    
    # 测试已加密密码不被重复加密
    double_encrypted = _encrypt_password(encrypted)
    assert double_encrypted == encrypted
    print("  ✓ 已加密密码不被重复加密")
    
except Exception as e:
    print(f"  ✗ 测试失败: {e}")
    sys.exit(1)

# 测试3: ComponentMonitor 方法存在性
print("\n[测试3] ComponentMonitor 方法存在性")
try:
    from monitors.component import ComponentMonitor
    monitor = ComponentMonitor()
    
    # 检查异步方法
    assert hasattr(monitor, '_check_mysql'), "缺少 _check_mysql 方法"
    assert hasattr(monitor, '_check_postgresql'), "缺少 _check_postgresql 方法"
    assert hasattr(monitor, '_check_dm'), "缺少 _check_dm 方法"
    assert hasattr(monitor, '_check_sqlserver'), "缺少 _check_sqlserver 方法"
    print("  ✓ 异步检测方法存在: _check_mysql, _check_postgresql, _check_dm, _check_sqlserver")
    
    # 检查同步方法
    assert hasattr(monitor, '_check_mysql_sync'), "缺少 _check_mysql_sync 方法"
    assert hasattr(monitor, '_check_postgresql_sync'), "缺少 _check_postgresql_sync 方法"
    assert hasattr(monitor, '_check_dm_sync'), "缺少 _check_dm_sync 方法"
    assert hasattr(monitor, '_check_sqlserver_sync'), "缺少 _check_sqlserver_sync 方法"
    print("  ✓ 同步检测方法存在: _check_mysql_sync, _check_postgresql_sync, _check_dm_sync, _check_sqlserver_sync")
    
    # 检查原有方法仍然存在
    assert hasattr(monitor, '_check_redis'), "缺少 _check_redis 方法"
    assert hasattr(monitor, '_check_rabbitmq'), "缺少 _check_rabbitmq 方法"
    print("  ✓ 原有方法保持不变: _check_redis, _check_rabbitmq")
    
except Exception as e:
    print(f"  ✗ 测试失败: {e}")
    sys.exit(1)

# 测试4: 分发逻辑正确性
print("\n[测试4] 分发逻辑正确性")
try:
    async def test_dispatch():
        # 测试不支持的类型
        result = await monitor.check({
            'target': 'unknown_db',
            'extra_config': {}
        })
        assert not result['is_normal']
        assert '不支持' in result['message']
        print("  ✓ 不支持的类型正确返回错误")
        
        # 测试 MySQL 分发（驱动可能未安装，但分发逻辑应正确路由）
        result = await monitor.check({
            'target': 'mysql',
            'extra_config': {'host': 'localhost', 'port': 3306}
        })
        # 不管连接是否成功，只要不是"不支持"的错误就说明分发正确
        assert '不支持' not in result.get('message', ''), "MySQL 未被正确分发"
        print("  ✓ MySQL 分发逻辑正确")
        
        # 测试 PostgreSQL 分发
        result = await monitor.check({
            'target': 'postgresql',
            'extra_config': {'host': 'localhost', 'port': 5432}
        })
        assert '不支持' not in result.get('message', ''), "PostgreSQL 未被正确分发"
        print("  ✓ PostgreSQL 分发逻辑正确")
        
        # 测试 DM 分发
        result = await monitor.check({
            'target': 'dm',
            'extra_config': {'host': 'localhost', 'port': 5236}
        })
        assert '不支持' not in result.get('message', ''), "DM 未被正确分发"
        print("  ✓ 达梦DM 分发逻辑正确")
        
        # 测试 SQL Server 分发
        result = await monitor.check({
            'target': 'sqlserver',
            'extra_config': {'host': 'localhost', 'port': 1433}
        })
        assert '不支持' not in result.get('message', ''), "SQL Server 未被正确分发"
        print("  ✓ SQL Server 分发逻辑正确")
    
    asyncio.run(test_dispatch())
except Exception as e:
    print(f"  ✗ 测试失败: {e}")
    sys.exit(1)

# 测试5: 驱动缺失时的降级处理
print("\n[测试5] 驱动缺失时的降级处理")
try:
    async def test_driver_missing():
        # 测试各数据库驱动缺失时的处理
        for db_type in ['mysql', 'postgresql', 'dm', 'sqlserver']:
            result = await monitor.check({
                'target': db_type,
                'extra_config': {'host': 'localhost', 'port': DB_DEFAULT_PORTS[db_type]}
            })
            if db_type not in _DB_DRIVERS:
                # 驱动未安装时应该返回 driver_missing 状态
                assert result.get('status') == 'driver_missing', \
                    f"{db_type} 驱动缺失时未返回 driver_missing 状态"
                assert '未安装' in result.get('message', ''), \
                    f"{db_type} 驱动缺失消息不正确"
                print(f"  ✓ {db_type} 驱动缺失时正确返回 driver_missing 状态")
            else:
                # 驱动已安装时，连接可能失败但不应该是 driver_missing
                assert result.get('status') != 'driver_missing', \
                    f"{db_type} 驱动已安装但返回了 driver_missing 状态"
                print(f"  ✓ {db_type} 驱动已安装，连接测试状态: {result.get('status')}")
    
    asyncio.run(test_driver_missing())
except Exception as e:
    print(f"  ✗ 测试失败: {e}")
    sys.exit(1)

# 测试6: 同步方法返回值结构验证
print("\n[测试6] 同步方法返回值结构验证")
try:
    for db_type in ['mysql', 'postgresql', 'dm', 'sqlserver']:
        sync_method = getattr(monitor, f'_check_{db_type}_sync')
        result = sync_method({'host': 'localhost', 'port': DB_DEFAULT_PORTS[db_type]})
        
        # 验证返回值结构
        assert 'is_normal' in result, f"{db_type} 返回值缺少 is_normal"
        assert 'status' in result, f"{db_type} 返回值缺少 status"
        assert 'message' in result, f"{db_type} 返回值缺少 message"
        
        if db_type not in _DB_DRIVERS:
            assert result['is_normal'] == False
            assert result['status'] == 'driver_missing'
        print(f"  ✓ {db_type} 同步方法返回值结构正确")
except Exception as e:
    print(f"  ✗ 测试失败: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("所有测试通过! ✓")
print("=" * 60)
