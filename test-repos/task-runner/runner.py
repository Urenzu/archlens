"""CLI entry point and main runner orchestration."""

import argparse
import json
import os
import sys
from cache import Cache, cached_run
from executor import run_sequence, summarize
from plugins import load_plugin_dir, load_builtin_plugins
from scheduler import Scheduler
from tasks import Task, TaskRegistry


def build_registry(plugin_dir: str = None) -> TaskRegistry:
    """Construct registry with built-in tasks plus any plugins."""
    registry = TaskRegistry()
    _register_defaults(registry)
    if plugin_dir:
        load_plugin_dir(plugin_dir, registry)
    return registry


def _register_defaults(registry: TaskRegistry):
    """Register a small set of built-in demo tasks."""
    registry.register(Task(name="lint", fn=_task_lint, tags=["ci"]))
    registry.register(Task(name="test", fn=_task_test, deps=["lint"], tags=["ci"]))
    registry.register(Task(name="build", fn=_task_build, deps=["test"], tags=["ci", "release"]))
    registry.register(Task(name="package", fn=_task_package, deps=["build"], tags=["release"]))
    registry.register(Task(name="deploy", fn=_task_deploy, deps=["package"], tags=["release"], retries=2))


def run_cli(argv=None):
    """Parse CLI args and dispatch to the scheduler."""
    parser = argparse.ArgumentParser(description="task-runner")
    parser.add_argument("targets", nargs="*", help="Tasks to run (default: all)")
    parser.add_argument("--tag", help="Run all tasks with this tag")
    parser.add_argument("--watch", action="store_true", help="Re-run on interval")
    parser.add_argument("--interval", type=int, default=10, help="Watch interval in seconds")
    parser.add_argument("--plugin-dir", help="Directory to load task plugins from")
    parser.add_argument("--context", help="JSON string of context variables")
    parser.add_argument("--cache", action="store_true", help="Enable result caching")
    parser.add_argument("--output", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    context = {}
    if args.context:
        try:
            context = json.loads(args.context)
        except json.JSONDecodeError as e:
            print(f"Invalid --context JSON: {e}", file=sys.stderr)
            sys.exit(1)

    registry = build_registry(args.plugin_dir)
    scheduler = Scheduler(registry)

    if args.watch:
        targets = args.targets or registry.all_names()
        scheduler.watch(targets, context, interval=args.interval)
        return

    if args.tag:
        summary = scheduler.run_tagged(args.tag, context)
    elif args.targets:
        summary = scheduler.run_targets(args.targets, context)
    else:
        summary = scheduler.run_all(context)

    _print_summary(summary, args.output)
    sys.exit(0 if summary["success"] else 1)


def _print_summary(summary: dict, fmt: str):
    if fmt == "json":
        print(json.dumps(summary, indent=2))
    else:
        ok = summary["counts"].get("ok", 0)
        fail = summary["counts"].get("failed", 0)
        skip = summary["counts"].get("skipped", 0)
        ms = summary["total_ms"]
        status = "PASS" if summary["success"] else "FAIL"
        print(f"{status} — {ok} ok, {fail} failed, {skip} skipped ({ms}ms)")


# ─── built-in task implementations ───────────────────────────────────────────

def _task_lint(ctx: dict):
    target = ctx.get("src", ".")
    # Vulnerability: shell=True with user-controlled src path
    import subprocess
    result = subprocess.run(f"flake8 {target}", shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Lint failed:\n{result.stdout}")
    return result.stdout


def _task_test(ctx: dict):
    import subprocess
    result = subprocess.run(["python", "-m", "pytest", "--tb=short", "-q"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Tests failed:\n{result.stdout}")
    return result.stdout


def _task_build(ctx: dict):
    src = ctx.get("src", "src")
    out = ctx.get("out", "dist")
    os.makedirs(out, exist_ok=True)
    return {"src": src, "out": out, "status": "built"}


def _task_package(ctx: dict):
    out = ctx.get("out", "dist")
    version = ctx.get("version", "0.1.0")
    archive = os.path.join(out, f"package-{version}.tar.gz")
    return {"archive": archive}


def _task_deploy(ctx: dict):
    env = ctx.get("env", "staging")
    if env == "production" and not ctx.get("confirmed"):
        raise RuntimeError("Production deploy requires confirmed=true in context")
    return {"env": env, "deployed": True}


if __name__ == "__main__":
    run_cli()
