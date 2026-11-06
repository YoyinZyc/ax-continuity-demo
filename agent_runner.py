#!/usr/bin/env python3
"""Autonomous 4-Stage ADK Coding Agent for AX Local-to-Cloud Continuity POC."""

import asyncio
import datetime
import os
import subprocess
import time
from pathlib import Path

import google.auth
from google.oauth2.credentials import Credentials

_creds = Credentials(token=os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN", "placeholder"))
_proj = os.environ.get("GOOGLE_CLOUD_PROJECT", "yczhou-gke-dev")
google.auth.default = lambda *a, **kw: (_creds, _proj)

from google.adk.agents import Agent
from google.adk.memory import VertexAiMemoryBankService
from google.adk.runners import Runner
from google.adk.sessions import VertexAiSessionService
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

WORKSPACE = Path(os.environ.get("AX_WORKSPACE_DIR", str(Path(__file__).resolve().parent)))
PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "yczhou-gke-dev")
ENGINE_LOCATION = os.environ.get("VERTEX_ENGINE_LOCATION", "us-central1")
ENGINE_ID = os.environ.get("AGENT_ENGINE_ID", "6400193688487591936")
RUN_ID = os.environ.get("AX_RUN_ID", "demo-run-01")
CLUSTER_CTX = os.environ.get("AX_CLUSTER_CONTEXT", "local")
PROMOTED_FROM = os.environ.get("AX_PROMOTED_FROM", "")
STAGE_PAUSE_SECONDS = int(os.environ.get("STAGE_PAUSE_SECONDS", "15"))


def log(msg: str) -> None:
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] [cluster={CLUSTER_CTX}] [run={RUN_ID}] {msg}"
    print(line, flush=True)


def read_workspace_file(rel_path: str) -> str:
    """Reads a text file from the repository workspace."""
    target = WORKSPACE / rel_path
    if not target.exists():
        return f"ERROR: {rel_path} does not exist"
    return target.read_text(encoding="utf-8")


def write_workspace_file(rel_path: str, content: str) -> str:
    """Writes content to a file inside the repository workspace."""
    target = WORKSPACE / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    log(f"  ✍️  Tool write_workspace_file: wrote {rel_path} ({len(content)} bytes)")
    return f"Successfully wrote {rel_path} ({len(content)} bytes)"


def run_shell_command(command: str) -> str:
    """Runs a shell command (such as pytest or python3 benchmark.py) in the workspace."""
    log(f"  ⚙️  Tool run_shell_command: {command}")
    proc = subprocess.run(
        command,
        shell=True,
        cwd=str(WORKSPACE),
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = (proc.stdout + "\n" + proc.stderr).strip()
    log(f"  📋 Command exit={proc.returncode}: {output.splitlines()[-1] if output else 'ok'}")
    return f"exit_code={proc.returncode}\n{output}"


def commit_and_push_stage(stage_number: int, summary: str) -> str:
    """Records stage completion in PROGRESS.md, commits all changes, and pushes to GitHub via Egress Gateway."""
    progress_file = WORKSPACE / "PROGRESS.md"
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    if not progress_file.exists():
        progress_file.write_text(
            "# Autonomous Agent Execution Progress\n\n"
            "| Stage | Cluster | Run ID | Timestamp | Summary |\n"
            "| :--- | :--- | :--- | :--- | :--- |\n",
            encoding="utf-8",
        )
    with progress_file.open("a", encoding="utf-8") as f:
        f.write(f"| Stage {stage_number} | `{CLUSTER_CTX}` | `{RUN_ID}` | {ts} | {summary} |\n")

    commit_msg = f"feat(stage-{stage_number}): {summary} [cluster:{CLUSTER_CTX}] [run:{RUN_ID}]"
    cmds = [
        ["git", "config", "user.name", "AX Autonomous Agent"],
        ["git", "config", "user.email", "ax-agent@ax.io"],
        ["git", "add", "-A"],
        ["git", "commit", "-m", commit_msg],
        ["git", "push", "origin", "HEAD:main"],
    ]
    for c in cmds:
        res = subprocess.run(c, cwd=str(WORKSPACE), capture_output=True, text=True)
        if res.returncode != 0 and "nothing to commit" not in (res.stdout + res.stderr):
            log(f"  ⚠️  git {' '.join(c[1:])} failed: {res.stderr.strip()}")
            return f"ERROR running {' '.join(c)}: {res.stderr}"

    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=str(WORKSPACE),
        capture_output=True,
        text=True,
    ).stdout.strip()
    log(f"  🚀 Tool commit_and_push_stage: pushed commit {sha} -> origin/main ({commit_msg})")
    return f"Committed and pushed {sha} to origin/main: {commit_msg}"


def completed_stages_in_git() -> dict[int, str]:
    """Checks git log in /workspace for stages already committed in this run."""
    subprocess.run(["git", "fetch", "origin", "main"], cwd=str(WORKSPACE), capture_output=True)
    subprocess.run(["git", "reset", "--hard", "origin/main"], cwd=str(WORKSPACE), capture_output=True)
    res = subprocess.run(
        ["git", "log", "--oneline", "-n", "20"],
        cwd=str(WORKSPACE),
        capture_output=True,
        text=True,
    )
    done: dict[int, str] = {}
    for line in res.stdout.splitlines():
        if f"[run:{RUN_ID}]" in line:
            for s in (1, 2, 3, 4):
                if f"feat(stage-{s}):" in line:
                    done[s] = line
    return done


STAGE_PROMPTS = {
    1: (
        "Execute STAGE 1 of BACKLOG.md: "
        "1) Read BACKLOG.md using read_workspace_file. "
        "2) Implement a clean, thread-safe SlidingWindowRateLimiter(max_requests: int, window_seconds: float) "
        "in 'src/rate_limiter.py' with methods allow(client_id: str) -> bool and remaining(client_id: str) -> int "
        "using collections.deque and threading.Lock. "
        "3) Call commit_and_push_stage(stage_number=1, summary='implement thread-safe SlidingWindowRateLimiter')."
    ),
    2: (
        "Execute STAGE 2 of BACKLOG.md: "
        "1) Write comprehensive pytest unit tests in 'tests/test_rate_limiter.py' testing allow(), deny when limit exceeded, "
        "per-client isolation, and remaining() count. "
        "2) Run 'PYTHONPATH=. pytest -v' via run_shell_command and ensure all tests pass. "
        "3) Call commit_and_push_stage(stage_number=2, summary='add unit test suite and verify pytest passes')."
    ),
    3: (
        "Execute STAGE 3 of BACKLOG.md: "
        "1) First check your session history and preloaded memory from Stages 1-2. "
        "2) Write 'benchmark.py' that benchmarks SlidingWindowRateLimiter across 5,000 requests and prints throughput (ops/sec). "
        "3) Run 'PYTHONPATH=. python3 benchmark.py' via run_shell_command. "
        "4) Call commit_and_push_stage(stage_number=3, summary='run cloud throughput benchmark on GKE')."
    ),
    4: (
        "Execute STAGE 4 of BACKLOG.md: "
        "1) Read 'PROGRESS.md' using read_workspace_file and recall all findings from Stages 1, 2, and 3 (including which stages ran on local Kind vs remote GKE). "
        "2) Write 'RELEASE_REPORT.md' summarizing the architecture, unit test results from local Kind, benchmark throughput from remote GKE, and continuity verification. "
        "3) Call commit_and_push_stage(stage_number=4, summary='publish cross-cluster RELEASE_REPORT.md')."
    ),
}


async def main() -> None:
    log("=================================================================")
    log("🤖 Starting AX Autonomous ADK Coding Agent")
    if PROMOTED_FROM:
        log(f"🔄 Task was PROMOTED via 'ax push' from cluster '{PROMOTED_FROM}' -> '{CLUSTER_CTX}'!")
    log("=================================================================")

    session_svc = VertexAiSessionService(
        project=PROJECT,
        location=ENGINE_LOCATION,
        agent_engine_id=ENGINE_ID,
    )
    memory_svc = VertexAiMemoryBankService(
        project=PROJECT,
        location=ENGINE_LOCATION,
        agent_engine_id=ENGINE_ID,
    )

    agent = Agent(
        name="ax_autonomous_engineer",
        model="gemini-3-flash-preview",
        instruction=(
            "You are an autonomous software engineering agent running inside an AX sandbox. "
            "Always use the provided tools to read/write files, run commands, and commit/push each completed stage. "
            "Maintain continuity across local Kind and remote GKE clusters using your session history and preloaded memories."
        ),
        tools=[
            PreloadMemoryTool(),
            read_workspace_file,
            write_workspace_file,
            run_shell_command,
            commit_and_push_stage,
        ],
    )

    runner = Runner(
        app_name=ENGINE_ID,
        agent=agent,
        session_service=session_svc,
        memory_service=memory_svc,
    )

    # Discover existing Vertex AI Session for this unique AX_RUN_ID, or create a new one
    existing_list = await session_svc.list_sessions(app_name=ENGINE_ID, user_id=RUN_ID)
    if existing_list.sessions:
        latest_id = existing_list.sessions[0].id
        session = await session_svc.get_session(
            app_name=ENGINE_ID,
            user_id=RUN_ID,
            session_id=latest_id,
        )
        log(f"🧠 Resumed existing Vertex AI Session: {session.id} (loaded {len(session.events)} prior events for run={RUN_ID})")
    else:
        session = await session_svc.create_session(
            app_name=ENGINE_ID,
            user_id=RUN_ID,
        )
        log(f"🆕 Created brand-new Vertex AI Session: {session.id} (for run={RUN_ID})")

    done_in_git = completed_stages_in_git()
    if done_in_git:
        log(f"📂 Detected already-committed stages in Git for run={RUN_ID}: {sorted(done_in_git.keys())}")
        for s_num, commit_line in sorted(done_in_git.items()):
            log(f"   ✓ Stage {s_num}: {commit_line}")

    for stage in (1, 2, 3, 4):
        done_in_git = completed_stages_in_git()
        if stage in done_in_git:
            log(f"⏭️  Skipping Stage {stage}/4 (already completed in earlier cluster session: {done_in_git[stage]})")
            continue

        log(f"▶️  Starting Stage {stage}/4 on cluster '{CLUSTER_CTX}'...")
        msg = types.Content(
            role="user",
            parts=[types.Part.from_text(text=f"[Current Cluster: {CLUSTER_CTX}] {STAGE_PROMPTS[stage]}")],
        )
        async for event in runner.run_async(
            user_id=RUN_ID,
            session_id=session.id,
            new_message=msg,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                for p in event.content.parts:
                    if p.text:
                        log(f"✅ Stage {stage}/4 Agent Summary: {p.text.strip().splitlines()[0]}")

        # Persist updated session events into Vertex AI Memory Bank
        updated_session = await session_svc.get_session(
            app_name=ENGINE_ID,
            user_id=RUN_ID,
            session_id=session.id,
        )
        await memory_svc.add_events_to_memory(
            app_name=ENGINE_ID,
            user_id=RUN_ID,
            events=updated_session.events,
            custom_metadata={"wait_for_completion": True},
        )
        log(f"💾 Stage {stage}/4 state synchronized to Vertex AI Session ({session.id}) & Memory Bank!")

        if stage < 4:
            log(f"⏸️  Stage {stage}/4 checkpoint complete. Waiting {STAGE_PAUSE_SECONDS}s before Stage {stage+1} (you can run 'ax push' now!)...")
            time.sleep(STAGE_PAUSE_SECONDS)

    log("🎉 All 4 Stages completed! Task finished.")


if __name__ == "__main__":
    asyncio.run(main())
