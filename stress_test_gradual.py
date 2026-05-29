#!/usr/bin/env python3
"""
漸進式壓力測試 — 300 → 3000 → 300 使用者
每階段 30 秒，記錄 HPA 擴展狀況
"""
import argparse
import asyncio
import json
import random
import subprocess
import time
from collections import Counter
from dataclasses import dataclass, field

import httpx

NTU_CENTER = (25.0173, 121.5397)

STEPS = [300, 500, 800, 1000, 1500, 2000, 2500, 3000,
         2500, 2000, 1500, 1000, 800, 500, 300]

STEP_DURATION = 30  # 每階段秒數


def jitter(lat, lng, radius=0.001):
    return lat + random.uniform(-radius, radius), lng + random.uniform(-radius, radius)


def run_cmd(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
    return r.stdout.strip()


def get_hpa_status():
    """Parse kubectl get hpa output"""
    out = run_cmd("kubectl get hpa -n realtime-map --no-headers 2>/dev/null")
    result = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 7:
            name = parts[0]
            target = parts[2]
            current = parts[3]
            min_rep = parts[4]
            max_rep = parts[5]
            replicas = parts[6]
            result[name] = {
                "target_cpu": target,
                "current_cpu": current,
                "min": int(min_rep),
                "max": int(max_rep),
                "replicas": int(replicas),
            }
    return result


def get_pod_count(app_name):
    out = run_cmd(f"kubectl get pods -n realtime-map -l app={app_name} --no-headers --field-selector=status.phase=Running 2>/dev/null")
    return len(out.splitlines())


@dataclass
class PhaseStats:
    success: int = 0
    failed: int = 0
    latencies: list[float] = field(default_factory=list)
    failures: Counter = field(default_factory=Counter)

    @property
    def total(self):
        return self.success + self.failed

    @property
    def success_rate(self):
        return self.success / self.total * 100 if self.total else 0


async def location_worker(client, user_id, target, stop_at, stats):
    lat, lng = jitter(*NTU_CENTER)
    while time.time() < stop_at:
        lat += random.uniform(-0.00008, 0.00008)
        lng += random.uniform(-0.00008, 0.00008)
        t0 = time.time()
        try:
            r = await client.post(f"{target}/locations", json={
                "user_id": user_id, "latitude": lat, "longitude": lng
            }, timeout=10)
            elapsed = time.time() - t0
            if r.is_success:
                stats.success += 1
            else:
                stats.failed += 1
                stats.failures[f"http_{r.status_code}"] += 1
            stats.latencies.append(elapsed)
        except (httpx.TimeoutException, httpx.ConnectError):
            stats.failed += 1
            stats.failures["error"] += 1
        await asyncio.sleep(random.uniform(0.5, 2.5))


async def event_worker(client, target, stop_at, stats):
    while time.time() < stop_at:
        lat, lng = jitter(*NTU_CENTER)
        t0 = time.time()
        try:
            r = await client.post(f"{target}/events", json={
                "title": random.choice(["交通事故", "施工中", "人群聚集", "設備故障", "道路封閉"]),
                "message": "壓測事件詳情",
                "description": "壓測事件",
                "severity": random.choice(["info", "urgent"]),
                "latitude": lat, "longitude": lng,
                "radius": 500, "expires_in": 30,
                "client_event_id": f"stress-{random.randint(1,999999)}",
            }, timeout=10)
            elapsed = time.time() - t0
            if r.is_success:
                stats.success += 1
            else:
                stats.failed += 1
                stats.failures[f"http_{r.status_code}"] += 1
            stats.latencies.append(elapsed)
        except (httpx.TimeoutException, httpx.ConnectError):
            stats.failed += 1
            stats.failures["error"] += 1
        await asyncio.sleep(random.uniform(2, 6))


async def run_phase(users, duration, event_target, location_target, timeout=10):
    stats_loc = PhaseStats()
    stats_evt = PhaseStats()
    stop_at = time.time() + duration
    limits = httpx.Limits(max_connections=users + 50, max_keepalive_connections=50)

    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        tasks = []
        # Location workers (80% of users)
        n_loc = int(users * 0.8)
        for i in range(n_loc):
            tasks.append(location_worker(client, f"user-{i}", location_target, stop_at, stats_loc))
        # Event workers (20% of users)
        n_evt = max(1, users - n_loc)
        for i in range(n_evt):
            tasks.append(event_worker(client, event_target, stop_at, stats_evt))

        await asyncio.gather(*tasks, return_exceptions=True)

    return stats_loc, stats_evt


def fmt_latency(lats):
    if not lats:
        return "N/A"
    s = sorted(lats)
    return f"avg={sum(s)/len(s)*1000:.0f}ms p50={s[len(s)//2]*1000:.0f}ms p95={s[int(len(s)*0.95)]*1000:.0f}ms"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-target", required=True)
    parser.add_argument("--location-target", required=True)
    parser.add_argument("--step-duration", type=int, default=30)
    parser.add_argument("--output", default="hpa_stress_log.jsonl")
    args = parser.parse_args()

    steps = STEPS
    step_dur = args.step_duration or STEP_DURATION

    print(f"""
╔═══════════════════════════════════════════════════╗
║   漸進式壓力測試 — HPA Auto-Scaling Demo         ║
║   {steps[0]} → {steps[len(steps)//2-1]} → {steps[-1]} 使用者                  ║
║   每階段 {step_dur}s，共 {len(steps)} 階段                    ║
╚═══════════════════════════════════════════════════╝
""")

    results = []
    total_start = time.time()

    for idx, n_users in enumerate(steps):
        phase_label = f"{'📈' if n_users > (steps[idx-1] if idx > 0 else 0) else '📉'}"
        print(f"\n{'='*60}")
        print(f"階段 {idx+1}/{len(steps)} {phase_label} {n_users} 使用者 ({step_dur}s)")
        print(f"{'='*60}")

        # HPA snapshot before
        hpa_before = get_hpa_status()
        loc_pods_before = get_pod_count("location-service")
        evt_pods_before = get_pod_count("event-service")
        print(f"  Before: loc_pods={loc_pods_before} evt_pods={evt_pods_before}")

        t0 = time.time()
        stats_loc, stats_evt = asyncio.run(run_phase(
            n_users, step_dur, args.event_target, args.location_target
        ))
        elapsed = time.time() - t0

        # HPA snapshot after
        time.sleep(3)  # let HPA controller settle
        hpa_after = get_hpa_status()
        loc_pods_after = get_pod_count("location-service")
        evt_pods_after = get_pod_count("event-service")

        loc_rps = stats_loc.success / elapsed if elapsed else 0
        evt_rps = stats_evt.success / elapsed if elapsed else 0

        record = {
            "phase": idx + 1,
            "users": n_users,
            "direction": "up" if (idx < len(steps)//2) else "down",
            "duration_s": round(elapsed, 1),
            "location": {
                "total": stats_loc.total, "success": stats_loc.success,
                "failed": stats_loc.failed, "success_rate": round(stats_loc.success_rate, 1),
                "rps": round(loc_rps, 1),
                "latency_ms": fmt_latency(stats_loc.latencies),
            },
            "event": {
                "total": stats_evt.total, "success": stats_evt.success,
                "failed": stats_evt.failed, "success_rate": round(stats_evt.success_rate, 1),
                "rps": round(evt_rps, 1),
                "latency_ms": fmt_latency(stats_evt.latencies),
            },
            "pods": {
                "location_before": loc_pods_before, "location_after": loc_pods_after,
                "event_before": evt_pods_before, "event_after": evt_pods_after,
            },
            "hpa": {
                "location_before": hpa_before.get("location-service-hpa", {}),
                "event_before": hpa_before.get("event-service-hpa", {}),
                "location_after": hpa_after.get("location-service-hpa", {}),
                "event_after": hpa_after.get("event-service-hpa", {}),
            },
        }

        results.append(record)
        with open(args.output, "a") as f:
            f.write(json.dumps(record) + "\n")

        # Pretty print
        print(f"  📍 Location: {stats_loc.success}/{stats_loc.total} ({stats_loc.success_rate:.1f}%) {loc_rps:.0f} RPS {fmt_latency(stats_loc.latencies)}")
        print(f"  📝 Event:    {stats_evt.success}/{stats_evt.total} ({stats_evt.success_rate:.1f}%) {evt_rps:.1f} RPS {fmt_latency(stats_evt.latencies)}")
        print(f"  📦 Pods:     loc {loc_pods_before}→{loc_pods_after}  evt {evt_pods_before}→{evt_pods_after}")

        loc_hpa = hpa_after.get("location-service-hpa", {})
        evt_hpa = hpa_after.get("event-service-hpa", {})
        if loc_hpa:
            print(f"  📊 HPA loc:  cpu {loc_hpa.get('current_cpu','?')}/{loc_hpa.get('target_cpu','?')}  replicas {loc_hpa.get('replicas','?')}")
        if evt_hpa:
            print(f"  📊 HPA evt:  cpu {evt_hpa.get('current_cpu','?')}/{evt_hpa.get('target_cpu','?')}  replicas {evt_hpa.get('replicas','?')}")

    total_time = time.time() - total_start
    print(f"""
{'='*60}
🏁 漸進式壓測完成！總時長 {total_time:.0f}s
{'='*60}
""")

    # Summary table
    print(f"{'階段':>4} {'使用者':>6} {'方向':>4} │ {'Loc成功率':>8} {'Loc RPS':>8} {'Loc延遲':>28} │ {'Evt成功率':>8} │ {'Loc Pods':>8} {'Evt Pods':>8}")
    print("-" * 120)
    for r in results:
        d = "📈" if r["direction"] == "up" else "📉"
        print(f"{r['phase']:>4} {r['users']:>6} {d:>4} │ {r['location']['success_rate']:>7.1f}% {r['location']['rps']:>8.1f} {r['location']['latency_ms']:>28} │ {r['event']['success_rate']:>7.1f}% │ {r['pods']['location_after']:>8} {r['pods']['event_after']:>8}")

    print(f"\n📊 詳細記錄已寫入: {args.output}")


if __name__ == "__main__":
    main()
