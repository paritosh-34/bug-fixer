"""
agent.py — the bug-fixer agent. Error trace in → fix applied.

Replaces the manual loop: copy error → paste into ChatGPT → copy fix back → re-run.
You only send the trace. The agent finds the file and line from it, reads the code,
edits it and re-runs to check.

How to run (from your project folder; needs BEDROCK_MODEL_ID + AWS_REGION in .env and AWS credentials):
    uv run python agent.py                           # paste the trace, then press Ctrl-D
    uv run buggy.py 2>&1 | uv run python agent.py    # or pipe the error straight in

Each edited file is saved as <file>.bak before its first edit, so you can reset:
    cp buggy.py.bak buggy.py
"""

import os
import sys

from dotenv import load_dotenv
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from tools import TOOL_MAP, TOOLS, WORKDIR

load_dotenv()

# Claude on Amazon Bedrock. AWS credentials come from ~/.aws (or AWS_* env vars), not .env keys.
llm = ChatBedrockConverse(
    model=os.environ["BEDROCK_MODEL_ID"],
    region_name=os.getenv("AWS_REGION", "us-east-1"),
).bind_tools(TOOLS)

SYSTEM = f"""You are a debugging agent. You are given an error trace from a Python project
in {WORKDIR}. You are not told which file is broken: work it out from the trace.

1. Find the frames in the trace that belong to the project (ignore .venv / site-packages frames).
   Read those files with read_file before changing anything.
2. Find the root cause of the error, not just the line where it crashed. If the cause is in
   another file (a caller, an import), read that file too.
3. Fix it with edit_file, making the smallest change that fixes the cause.
4. Verify: run the script the trace started from (the first project frame, usually `<module>`)
   with run_file. If it still fails or a new error appears, repeat from step 2.
5. Never hide an error: no try/except to swallow it, no deleting the failing code.
6. If the error is not a code bug (missing package, missing env variable, a file or service
   that doesn't exist), do not edit code. Say what the user needs to do instead.

Reply with:
- Root cause: one or two sentences
- Change: which file and what you edited (or "none" for a non-code problem)
- Result: the output of the final run, or "not verified" and why"""

MAX_STEPS = 15  # safety net so a confused model can't loop (and bill you) forever


def run_agent(error: str) -> str:
    messages = [
        SystemMessage(content=SYSTEM),
        HumanMessage(content=f"Error trace:\n{error}"),
    ]

    for _ in range(MAX_STEPS):
        response = llm.invoke(messages)          # Reason
        messages.append(response)

        if not response.tool_calls:              # no tool requested → final answer
            return response.text

        for tc in response.tool_calls:           # Act
            print(f"  [tool] {tc['name']}({', '.join(f'{k}={v!r}' for k, v in tc['args'].items())[:120]})")
            result = TOOL_MAP[tc["name"]].invoke(tc["args"])
            messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))  # Observe

    return "Stopped after too many steps without a clean run."


if __name__ == "__main__":
    if sys.stdin.isatty():
        print("Paste the error trace, then press Ctrl-D:\n")
    error = sys.stdin.read().strip()
    if not error:
        sys.exit("No error trace given.")

    print("\nFixing...\n")
    print(run_agent(error))
