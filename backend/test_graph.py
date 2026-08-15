"""
test_graph.py
-------------
Quick script to run the agent graph and write the generated game files to disk.

Usage:
    python test_graph.py "make a simple snake game"

The generated files will be saved to ./generated_game/
"""

import sys
import os
from pathlib import Path

# Ensure the backend dir is on the path
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from agents import graph


def main():
    # Get the prompt from command line or use a default
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        prompt = "Create a simple snake game where the snake eats food and grows longer"

    print(f"\n{'='*60}")
    print(f"  Running agent graph with prompt:")
    print(f"  \"{prompt}\"")
    print(f"{'='*60}\n")

    # Initial state
    initial_state = {
        "user_prompt": prompt,
        "creative_vision": None,
        "design_doc": None,
        "files": {},
        "qa_report": None,
        "retry_count": 0,
        "errors": [],
    }

    # Run the graph
    final_state = graph.invoke(initial_state)

    # Print results
    print(f"\n{'='*60}")
    print("  CREATIVE VISION")
    print(f"{'='*60}")
    vision = final_state["creative_vision"]
    print(f"  Title: {vision.game_title}")
    print(f"  Theme: {vision.theme}")
    print(f"  Visual Style: {vision.visual_style}")
    print(f"  Mood: {vision.mood}")
    print(f"  Target Feel: {vision.target_feel}")

    print(f"\n{'='*60}")
    print("  DESIGN DOC")
    print(f"{'='*60}")
    design = final_state["design_doc"]
    print(f"  Controls: {design.player_controls}")
    print(f"  Core Loop: {design.core_loop}")
    print(f"  Win: {design.win_condition}")
    print(f"  Lose: {design.lose_condition}")
    print(f"  Entities: {', '.join(design.entities)}")
    print(f"  Level: {design.level_structure}")

    print(f"\n{'='*60}")
    print("  GENERATED FILES")
    print(f"{'='*60}")
    files = final_state["files"]
    if not files:
        print("  No files were generated!")
        return

    # Write files to ./generated_game/
    output_dir = Path(__file__).parent / "generated_game"
    output_dir.mkdir(exist_ok=True)

    for file_path, content in files.items():
        full_path = output_dir / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        print(f"  Written: {file_path} ({len(content)} bytes)")

    print(f"\n{'='*60}")
    print("  QA REPORT")
    print(f"{'='*60}")
    qa = final_state["qa_report"]
    if qa:
        print(f"  Passed: {qa.passed}")
        if qa.errors:
            print(f"  Errors:")
            for err in qa.errors:
                print(f"    - {err}")
        if qa.suggestions:
            print(f"  Suggestions:")
            for s in qa.suggestions:
                print(f"    - {s}")

    print(f"\n{'='*60}")
    print(f"  Game files saved to: {output_dir.resolve()}")
    print(f"  Retries used: {final_state['retry_count']}")
    print(f"{'='*60}")
    print(f"\n  To test: open generated_game/index.html in your browser")
    print(f"  (If it uses TypeScript, compile first: npx tsc -p generated_game/tsconfig.json)")


if __name__ == "__main__":
    main()
