"""Thin CLI wrapping the engine/narrator/RAG modules — `pyproject.toml`'s `landfall`
console-script entry point. No orchestration framework, per CLAUDE.md's engineering
rules: this is argparse dispatch to functions that already exist elsewhere.
"""

import argparse

from landfall.impact.engine import ROICoverageError, run, run_baseline
from landfall.llm.compiler import compile_scenario
from landfall.llm.rag_answer import answer_verified
from landfall.scenario import ScenarioConfig
from landfall.storms import STORMS
from landfall.verify.verified_narrator import narrate_verified


def _add_perturbation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("storm", choices=sorted(STORMS))
    parser.add_argument("--offset-km", type=float, default=0.0, dest="track_offset_km")
    parser.add_argument("--bearing", type=float, default=0.0, dest="track_bearing_deg")
    parser.add_argument("--intensity-delta", type=float, default=0.0, dest="intensity_delta_kn")


def _scenario_from_args(args: argparse.Namespace) -> ScenarioConfig:
    return ScenarioConfig(
        storm_key=args.storm,
        track_offset_km=args.track_offset_km,
        track_bearing_deg=args.track_bearing_deg,
        intensity_delta_kn=args.intensity_delta_kn,
    )


def _print_result(result: dict) -> None:
    damage_range = result["total_damage_usd_range"]
    print(f"Total damage (USD): {result['total_damage_usd']:,.2f} point estimate "
          f"(range: {damage_range['low']:,.2f} - {damage_range['high']:,.2f})")
    print(f"Affected population: {result['affected_population']:,.0f}")
    print("Top municipalities by damage:")
    for row in result["damage_by_municipality"][:5]:
        print(f"  {row['municipality']}, {row['province']}: ${row['damage_usd']:,.2f}")


def cmd_run(args: argparse.Namespace) -> None:
    scenario = _scenario_from_args(args)
    try:
        result = run_baseline(args.storm) if scenario.is_historical_baseline() else run(scenario)
    except ROICoverageError as e:
        print(f"Refused: {e}")
        return
    _print_result(result)


def cmd_narrate(args: argparse.Namespace) -> None:
    scenario = _scenario_from_args(args)
    try:
        result = run_baseline(args.storm) if scenario.is_historical_baseline() else run(scenario)
    except ROICoverageError as e:
        print(f"Refused: {e}")
        return
    year = STORMS[args.storm].year
    if scenario.is_historical_baseline():
        description = f"Historical replay of Typhoon {args.storm.title()} ({year})."
    else:
        description = (
            f"Counterfactual based on Typhoon {args.storm.title()} ({year}): track shifted "
            f"{scenario.track_offset_km} km at bearing {scenario.track_bearing_deg}°, "
            f"intensity changed by {scenario.intensity_delta_kn:+} kn."
        )
    damage_range = result["total_damage_usd_range"]
    text, raw_report, final_report = narrate_verified(
        description,
        damage_range["low"],
        damage_range["high"],
        result["affected_population"],
        permitted_values=[year],
    )
    print(text)
    print(f"\n[groundedness: {final_report.grounded_claims}/{final_report.total_claims} final, "
          f"{raw_report.grounded_claims}/{raw_report.total_claims} raw]")


def cmd_compile(args: argparse.Namespace) -> None:
    result = compile_scenario(args.text)
    if result.rejected:
        print(f"Refused: {result.refusal}")
    else:
        print(result.config.model_dump())


def cmd_ask(args: argparse.Namespace) -> None:
    text, results, _raw_report, final_report = answer_verified(args.question, storm_key=args.storm)
    print(text)
    print(f"\n[groundedness: {final_report.grounded_claims}/{final_report.total_claims}]")
    print("\nSources:")
    for i, r in enumerate(results, start=1):
        print(f"  [{i}] {r['source_file']}, p.{r['page']}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="landfall", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_run = subparsers.add_parser("run", help="Run a historical or counterfactual scenario")
    _add_perturbation_args(p_run)
    p_run.set_defaults(func=cmd_run)

    p_narrate = subparsers.add_parser("narrate", help="Run a scenario and narrate the cached result")
    _add_perturbation_args(p_narrate)
    p_narrate.set_defaults(func=cmd_narrate)

    p_compile = subparsers.add_parser("compile", help="Compile a natural-language scenario request")
    p_compile.add_argument("text")
    p_compile.set_defaults(func=cmd_compile)

    p_ask = subparsers.add_parser("ask", help="Ask the RAG interrogator about a sitrep")
    p_ask.add_argument("question")
    p_ask.add_argument("--storm", choices=sorted(STORMS), default=None)
    p_ask.set_defaults(func=cmd_ask)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
