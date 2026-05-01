import asyncio
from engine.strategy_analyzer import analyze_target

async def main():
    result = await analyze_target(
        target_binary="target/vulnerable",
        seed_dir="seeds",
        custom_description="Custom input structure: binary file using magic headers, extremely prone to bit flips."
    )
    print("Raw Response:")
    print(repr(result["raw_response"]))
    print("Selected:", result["selected_algorithms"])

asyncio.run(main())
