# 请求体上限（413）回归：超过 MAX_CONTENT_LENGTH（8MB）的请求应在读取 body 前被拒绝，
# 且错误响应保持统一 JSON 信封（Flask 默认 413 是 HTML 错误页，前端按 {code,message,data} 解不出提示）
import io


def test_oversized_upload_returns_json_413(app_ctx, user_headers):
    client = app_ctx.test_client()
    big = io.BytesIO(b'\0' * (8 * 1024 * 1024 + 1024))
    res = client.post('/api/pools/images', headers=user_headers,
                      data={'file': (big, 'big.jpg')})
    assert res.status_code == 413
    body = res.get_json()
    assert body['code'] == 4130
    assert '8MB' in body['message']


def test_body_under_limit_reaches_business_layer(app_ctx, user_headers):
    """8MB 内的请求照常进入业务层：此处 1MB 非图片内容应由图片校验以 400 拒绝，
    证明上限没有误伤正常体积的请求"""
    client = app_ctx.test_client()
    small = io.BytesIO(b'\0' * (1024 * 1024))
    res = client.post('/api/pools/images', headers=user_headers,
                      data={'file': (small, 'fake.jpg')})
    assert res.status_code == 400
    assert res.get_json()['code'] == 4333
