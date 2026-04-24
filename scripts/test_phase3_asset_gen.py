#!/usr/bin/env python3
"""
Phase3 资产生成端到端自动化测试

测试内容：
1. 创建项目、上传剧本（multipart）、解析剧本（2集）
2. 等待解析完成，确认分集规划（含 episodes body）
3. 等待资产生成任务（assets_confirmed 前）
4. 验证触发生成后状态变为 queued
5. 验证防重复入队（queued 状态再次调用返回 skipped）
6. 等待所有资产生成完成，验证 preview_url 非空
7. 验证最终状态为 pending（等用户确认）
"""
import sys
import io
import time
import json
import requests

BASE = "http://localhost:8000/api/v1"
TIMEOUT = 300  # 等待生成最多 5 分钟

SCRIPT_TEXT = """
第一集：起步
阿杰是一个租住在城中村的年轻程序员，每天面对双显示器写代码。
他的合租客厅里住着另一个室友大飞，是个整天做白日梦的人。
某天阿杰在K线图界面上发现了一个规律，准备用代码来验证。

第二集：验证
阿杰熬夜用笔记本电脑写完了交易程序，配合手机短信提醒。
大飞凑过来看，眼镜反着光，好奇地问策略是否可行。
两人吃着泡面讨论到深夜，电脑椅嘎吱嘎吱地响着。
""".strip()


def ok(label):
    print(f"  ✓ {label}")


def fail(label, detail=""):
    print(f"  ✗ {label}", file=sys.stderr)
    if detail:
        print(f"    {detail}", file=sys.stderr)
    sys.exit(1)


def api(method, path, **kwargs):
    url = f"{BASE}{path}"
    r = getattr(requests, method)(url, timeout=30, **kwargs)
    if not r.ok:
        raise RuntimeError(f"{method.upper()} {path} → {r.status_code}: {r.text[:400]}")
    if r.status_code == 204:
        return {}
    return r.json()


def poll(fn, condition, interval=4, timeout=TIMEOUT, label="等待条件"):
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = fn()
        if condition(result):
            return result
        print(f"    ... {label} ({int(deadline - time.time())}s 剩余)")
        time.sleep(interval)
    fail(f"超时: {label}")


def main():
    print("\n=== Phase3 资产生成端到端测试 ===\n")

    # 1. 创建项目
    print("[1] 创建项目")
    proj = api("post", "/projects", json={"title": "自动化测试项目", "genre": "都市"})
    pid = proj["id"]
    ok(f"项目创建成功: {pid}")

    # 2. 上传剧本（multipart）
    print("[2] 上传剧本")
    script_bytes = SCRIPT_TEXT.encode("utf-8")
    api("post", f"/projects/{pid}/upload-script",
        files={"file": ("script.txt", io.BytesIO(script_bytes), "text/plain")})
    ok("剧本上传成功")

    # 3. 触发解析（目标 2 集）
    print("[3] 触发剧本解析（目标 2 集）")
    task_info = api("post", f"/generate/projects/{pid}/parse-script",
                    json={"target_episodes": 2, "min_duration": 60, "parse_notes": ""})
    ok(f"解析任务已入队: {task_info}")

    # 4. 等待解析完成（init_status 达到 episodes_confirmed 之前至少有 episodes）
    print("[4] 等待剧本解析完成...")
    poll(
        fn=lambda: api("get", f"/projects/{pid}"),
        condition=lambda p: p["init_status"] in (
            "episodes_confirmed", "assets_confirmed", "initialized"
        ) or len(api("get", f"/projects/{pid}/episodes")) > 0,
        label="等待 init_status >= 解析完成",
        timeout=180,
    )

    episodes = api("get", f"/projects/{pid}/episodes")
    ep_count = len(episodes)
    if ep_count != 2:
        fail(f"期望 2 集，实际 {ep_count} 集", json.dumps(episodes, ensure_ascii=False))
    ok(f"分集数量正确: {ep_count} 集")

    # 5. 确认分集规划（传入 episodes 数据）
    print("[5] 确认分集规划")
    ep_payload = [
        {
            "id": ep.get("id"),
            "number": ep["number"],
            "title": ep["title"],
            "summary": ep.get("summary", ""),
            "word_count": ep.get("word_count", 500),
            "estimated_duration": ep.get("estimated_duration", 60),
        }
        for ep in episodes
    ]
    api("post", f"/projects/{pid}/confirm-episodes", json={"episodes": ep_payload})
    ok("分集规划已确认")

    # 6. 等待资产生成（init_status = assets_confirmed 代表 LLM 已生成资产 meta）
    print("[6] 等待 LLM 生成资产清单...")
    poll(
        fn=lambda: api("get", f"/projects/{pid}"),
        condition=lambda p: p["init_status"] in ("assets_confirmed", "initialized")
            or len(api("get", f"/projects/{pid}/assets")) > 0,
        label="等待资产列表生成",
        timeout=180,
    )

    assets = api("get", f"/projects/{pid}/assets")
    if not assets:
        fail("资产列表为空，LLM 未生成资产")
    ok(f"资产数量: {len(assets)}")

    # 7. 触发第一个资产生成，验证状态变为 queued
    print("[7] 触发单个资产生成，验证 queued 状态")
    a0 = next((a for a in assets if not a.get("preview_url")), assets[0])
    resp = api("post", f"/generate/assets/{a0['id']}/image")
    if resp.get("skipped"):
        print(f"    资产 {a0['name']} 已在队列（上次测试遗留），跳过 queued 验证")
    else:
        ok(f"触发成功，task_id={resp.get('task_id')}")
        time.sleep(1)
        refreshed_list = api("get", f"/projects/{pid}/assets")
        a0_data = next((a for a in refreshed_list if a["id"] == a0["id"]), None)
        if not a0_data:
            fail("无法找到资产")
        if a0_data["status"] not in ("queued", "generating", "pending"):
            fail(f"触发后状态异常: {a0_data['status']}")
        ok(f"触发后状态: {a0_data['status']}")

        # 8. 验证防重复入队
        print("[8] 验证防重复入队")
        if a0_data["status"] in ("queued", "generating"):
            resp2 = api("post", f"/generate/assets/{a0['id']}/image")
            if not resp2.get("skipped"):
                fail(f"应该返回 skipped=True，实际: {resp2}")
            ok("防重复入队生效，返回 skipped=True")
        else:
            print("    资产已生成完成，跳过防重复测试（正常）")

    # 9. 触发所有剩余资产生成
    print("[9] 触发所有资产批量生成")
    all_assets = api("get", f"/projects/{pid}/assets")
    triggered = 0
    skipped = 0
    for a in all_assets:
        if not a.get("preview_url"):
            try:
                r = api("post", f"/generate/assets/{a['id']}/image")
                if r.get("skipped"):
                    skipped += 1
                else:
                    triggered += 1
            except Exception as e:
                print(f"    警告: 触发 {a['name']} 失败: {e}")
    ok(f"触发 {triggered} 个，跳过（已在队列）{skipped} 个")

    # 10. 等待所有资产生成完成（有 preview_url）
    print("[10] 等待所有资产生成完成...")
    final_assets = poll(
        fn=lambda: api("get", f"/projects/{pid}/assets"),
        condition=lambda lst: all(a.get("preview_url") for a in lst),
        interval=5,
        timeout=TIMEOUT,
        label="等待所有资产 preview_url 非空",
    )
    ok(f"所有 {len(final_assets)} 个资产生成完成")

    # 11. 验证最终状态
    print("[11] 验证资产最终状态")
    bad = [a for a in final_assets if a["status"] not in ("pending", "approved")]
    if bad:
        fail(f"有资产状态异常: {[(a['name'], a['status']) for a in bad]}")
    ok("所有资产状态为 pending（等待用户确认）或 approved")

    print(f"\n=== 全部测试通过 ✓（共 {len(final_assets)} 个资产）===\n")

    # 12. 清理测试项目
    print("[清理] 删除测试项目")
    try:
        api("delete", f"/projects/{pid}")
        ok(f"测试项目 {pid} 已删除")
    except Exception as e:
        print(f"    警告: 删除失败（不影响测试结果）: {e}")


if __name__ == "__main__":
    main()
