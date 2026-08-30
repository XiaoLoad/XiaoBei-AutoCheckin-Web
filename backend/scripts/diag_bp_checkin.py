# 提交签到真机诊断脚本（模块 E 联调用，不入自动化）
# 用法（backend 目录下）：
#   查看任务（默认，不提交）：
#     python scripts/diag_bp_checkin.py --account 手机号 --password 密码 --type dorm
#   真实提交（无图）：
#     python scripts/diag_bp_checkin.py --account ... --password ... --type dorm --submit
#   真实提交（带图）：
#     python scripts/diag_bp_checkin.py --account ... --password ... --type dorm --submit --image path/to.jpg
# 可选：--lat/--lng/--address/--remark 覆盖提交字段；--type activity 走 sign 镜像契约（待真机核准）
import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.b_platform.real import RealAdapter  # noqa: E402
from app.services.geo import apply_location_jitter, haversine_m  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description='小北平台提交签到诊断')
    ap.add_argument('--account', required=True)
    ap.add_argument('--password', required=True)
    ap.add_argument('--type', default='dorm', choices=['dorm', 'activity'])
    ap.add_argument('--submit', action='store_true', help='真实提交（默认仅查看与构造）')
    ap.add_argument('--image', default='', help='提交图片路径（缺省走无图接口）')
    ap.add_argument('--lat', default='')
    ap.add_argument('--lng', default='')
    ap.add_argument('--address', default='')
    ap.add_argument('--remark', default='签到')
    args = ap.parse_args()

    adapter = RealAdapter()
    res = adapter.verify_and_fetch(args.account, args.password)
    token = res.token
    session = {'token': token, 'ua': None}
    print(f'[1] 登录成功 bp_uid={res.bp_uid} profile={json.dumps(res.profile, ensure_ascii=False)}')

    ctx = adapter.find_active_task(session, args.type)
    if ctx is None:
        print('[2] 当前无进行中的签到任务（list 无 isFinish==0 的行）')
        return
    task, fence = ctx['task'], ctx['fence']
    print(f"[2] 进行中任务：id={task['id']} name={task['taskName']} needPhoto={task['needPhoto']} "
          f"window={task.get('startTime')}~{task.get('endTime')}")
    print(f"    围栏：{json.dumps(fence, ensure_ascii=False)}")

    # 定位：优先命令行坐标；否则用围栏中心 ±10m
    if args.lat and args.lng:
        lat, lng = apply_location_jitter(args.lat, args.lng, 10)
    elif fence:
        lat, lng = apply_location_jitter(fence[0].get('latitude'), fence[0].get('longitude'), 10)
    else:
        lat, lng = '', ''
    location = f'{lng}:{lat}' if lat and lng else ''
    dist = (haversine_m(lat, lng, fence[0].get('latitude'), fence[0].get('longitude'))
            if (lat and fence) else None)
    print(f"[3] 提交定位：{location or '（空）'}"
          + (f'（距围栏中心 {int(dist)} 米 / 半径 {fence[0].get("radius")} 米）' if dist is not None and fence else ''))

    image = None
    if args.image:
        with open(args.image, 'rb') as f:
            image = {'bytes': f.read(), 'filename': None}
        print(f'[4] 图片：{args.image}（{len(image["bytes"])} 字节，提交时按 JPEG 规范命名）')

    if not args.submit:
        print('[5] 未加 --submit，仅构造不发送（DryRun）。字段：'
              + json.dumps({'location': location, 'address': args.address,
                            'remark': args.remark, 'size': '1' if image else '0'}, ensure_ascii=False))
        return

    result = adapter.submit_checkin(session, args.type, task['id'], location,
                                    args.address, args.remark, image)
    print(f"[5] 提交结果：status={result.status} ok={result.ok}")
    print(f"    reason={result.fail_reason}")
    print(f"    detail={json.dumps(result.detail, ensure_ascii=False, default=str)}")


if __name__ == '__main__':
    main()
