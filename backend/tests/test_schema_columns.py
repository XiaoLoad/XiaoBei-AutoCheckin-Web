# 模型补列验证：工厂启动（create_all + 幂等 ALTER）后列必须齐全
from sqlalchemy import inspect as sa_inspect

from app.extensions import db


def test_pool_columns_exist(app_ctx):
    insp = sa_inspect(db.engine)

    loc_cols = {c['name'] for c in insp.get_columns('pool_locations')}
    assert {'offset_m', 'is_system'} <= loc_cols

    ua_cols = {c['name'] for c in insp.get_columns('pool_uas')}
    assert 'is_system' in ua_cols

    img_cols = {c['name'] for c in insp.get_columns('pool_images')}
    assert 'trashed_at' in img_cols


def test_upload_dir_config(app):
    assert app.config['UPLOAD_DIR']
