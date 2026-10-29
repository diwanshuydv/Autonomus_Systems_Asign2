"""Interactive command-line chat with the Academic Helpdesk.

    python chat.py                      # multi-agent, default model (qwen3:1.7b)
    python chat.py --mode single        # single-agent baseline
    python chat.py --mode multi-transfer  # ADK native transfer_to_agent delegation (needs an 8B model)
    python chat.py --model ollama_chat/llama3.1:8b --trace
    python chat.py -q "What is the slot for Autonomous Systems?"
"""
import argparse
import asyncio
import json

from helpdesk.runner import HelpdeskRunner


def show(result: dict, trace: bool):
    if trace:
        print(f"  agents: {' -> '.join(result['agents'])}")
        for call in result["tool_calls"]:
            print(f"  tool:   {call['agent']}.{call['name']}({json.dumps(call['args'], ensure_ascii=False)})")
        print(f"  time:   {result['latency_s']}s" + ("   [logged for human review]" if result["logged"] else ""))
    print(f"\nHelpdesk: {result['answer']}\n")


async def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["multi", "multi-transfer", "single"], default="multi")
    parser.add_argument("--model", default=None, help="LiteLLM model id, e.g. ollama_chat/qwen3:8b")
    parser.add_argument("--trace", action="store_true", help="show agent hand-offs and tool calls")
    parser.add_argument("-q", "--question", help="ask one question and exit")
    args = parser.parse_args()

    bot = HelpdeskRunner(mode=args.mode, model=args.model)
    if args.question:
        show(await bot.ask(args.question), trace=True)
        return
    print(f"IIT Jodhpur Academic Helpdesk ({args.mode}-agent, {bot.model}). Type 'exit' to quit, 'new' for a new session.")
    while True:
        try:
            q = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"exit", "quit"}:
            break
        if q.lower() == "new":
            await bot.new_session()
            continue
        if q:
            show(await bot.ask(q), args.trace)


if __name__ == "__main__":
    asyncio.run(main())
