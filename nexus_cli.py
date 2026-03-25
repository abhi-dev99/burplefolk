import argparse
import json
from pathlib import Path
from typing import Dict, List

import pandas as pd

from nexus.ai import ollama_get_models
from nexus.analysis import run_analysis
from nexus.audit import audit_commit
from nexus.models import DBConnectionConfig
from nexus.orchestration import orchestrate_llm_task


def _load_csv_files(csv_paths: List[str]) -> Dict[str, bytes]:
    file_map: Dict[str, bytes] = {}
    for p in csv_paths:
        path = Path(p)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"CSV file not found: {path}")
        file_map[path.name] = path.read_bytes()
    return file_map


def _load_sqlite_file(sqlite_path: str) -> Dict[str, bytes]:
    path = Path(sqlite_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"SQLite file not found: {path}")
    return {path.name: path.read_bytes()}


def _save_outputs(analysis: Dict, out_dir: Path, ai_brief: str = "") -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    full_export = {
        "generated_at": analysis["generated_at"],
        "source_type": analysis["source_type"],
        "avg_quality_score": analysis["avg_quality_score"],
        "table_profiles": analysis["table_profiles"],
        "relationships": analysis["relationships"],
        "business_context": analysis["business_context"],
        "ai_brief": ai_brief,
    }

    (out_dir / "nexus_analysis.json").write_text(json.dumps(full_export, indent=2, default=str), encoding="utf-8")
    analysis["dictionary"].to_csv(out_dir / "data_dictionary.csv", index=False)
    pd.DataFrame(analysis["relationships"]).to_csv(out_dir / "relationships.csv", index=False)
    (out_dir / "er_diagram.mmd").write_text(analysis["mermaid"], encoding="utf-8")
    (out_dir / "er_graph.html").write_text(analysis["er_html"], encoding="utf-8")

    quality_df = pd.DataFrame(
        [
            {
                "table": p["table"],
                "quality_score": p["quality_score"],
                "base_quality_score": p.get("base_quality_score", p["quality_score"]),
                "completeness_score": p["completeness_score"],
                "consistency_score": p["consistency_score"],
                "temporal_bonus_points": p.get("temporal_bonus_points", 0.0),
                "duplicate_pk_records": p["duplicate_pk_records"],
                "issues": " | ".join(p["issues"]),
            }
            for p in analysis["table_profiles"]
        ]
    )
    quality_df.to_csv(out_dir / "quality_report.csv", index=False)

    if ai_brief:
        (out_dir / "ai_brief.txt").write_text(ai_brief, encoding="utf-8")


def _print_summary(analysis: Dict) -> None:
    print("=== Nexus CLI Summary ===")
    print(f"generated_at: {analysis['generated_at']}")
    print(f"source_type: {analysis['source_type']}")
    print(f"tables: {len(analysis['table_profiles'])}")
    print(f"relationships: {len(analysis['relationships'])}")
    print(f"avg_quality_score: {analysis['avg_quality_score']}")

    print("\nTop table quality:")
    quality_df = pd.DataFrame(
        [{"table": p["table"], "quality_score": p["quality_score"]} for p in analysis["table_profiles"]]
    ).sort_values("quality_score")
    print(quality_df.to_string(index=False))


def cmd_models(args: argparse.Namespace) -> None:
    models = ollama_get_models(args.ollama_endpoint)
    if not models:
        print("No Ollama models detected or server unreachable.")
        return
    print("Detected Ollama models:")
    for m in models:
        print(f"- {m}")


def cmd_analyze(args: argparse.Namespace) -> None:
    if args.source == "csv":
        if not args.csv:
            raise ValueError("Provide at least one CSV file with --csv")
        file_map = _load_csv_files(args.csv)
        source_type = "CSV Bundle"
        db_cfg = None
    elif args.source == "sqlite":
        if not args.sqlite:
            raise ValueError("Provide a SQLite DB file with --sqlite")
        file_map = _load_sqlite_file(args.sqlite)
        source_type = "SQLite"
        db_cfg = None
    else:
        source_type = "DB Connection"
        file_map = {"db_connection": b"ready"}
        if not (args.db_type and args.host and args.port and args.database and args.username):
            raise ValueError("For --source db, provide --db-type --host --port --database --username (and optionally --password)")
        db_cfg = DBConnectionConfig(
            db_type=args.db_type,
            host=args.host,
            port=args.port,
            database=args.database,
            username=args.username,
            password=args.password or "",
            driver=args.driver,
        )

    analysis = run_analysis(
        source_type,
        file_map,
        args.profile_limit,
        db_config=db_cfg,
        erd_view_mode=args.erd_view,
        erd_layout_direction=args.erd_layout,
    )
    if not analysis:
        raise RuntimeError("No analysis generated. Check your input files.")

    _print_summary(analysis)

    ai_brief = ""
    if args.ai_brief:
        model = args.model
        if not model:
            available = ollama_get_models(args.ollama_endpoint)
            model = available[0] if available else "llama3:latest"
        print(f"\nGenerating AI brief with orchestrator using model: {model}")
        orchestrated = orchestrate_llm_task(
            analysis=analysis,
            task="executive_brief",
            provider_preference="ollama",
            fallback_provider=None,
            ollama_model=model,
            ollama_endpoint=args.ollama_endpoint,
            gemini_model="gemini-2.0-flash",
            gemini_api_key="",
            timeout_seconds=120,
        )
        ai_brief = str(orchestrated.get("output", "")).strip()
        print("\n=== AI Brief ===")
        print(ai_brief)

    out_dir = Path(args.out_dir)
    _save_outputs(analysis, out_dir, ai_brief=ai_brief)
    print(f"\nArtifacts written to: {out_dir.resolve()}")

    if args.commit_audit:
        entry = audit_commit(
            {
                "generated_at": analysis["generated_at"],
                "source_type": analysis["source_type"],
                "avg_quality_score": analysis["avg_quality_score"],
                "table_profiles": analysis["table_profiles"],
                "relationships": analysis["relationships"],
                "business_context": analysis["business_context"],
                "ai_brief": ai_brief,
            },
            actor=args.actor,
        )
        print("\nAudit snapshot committed:")
        print(json.dumps(entry, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Nexus Intelligence CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_models = sub.add_parser("models", help="List local Ollama models")
    p_models.add_argument("--ollama-endpoint", default="http://localhost:11434")
    p_models.set_defaults(func=cmd_models)

    p_analyze = sub.add_parser("analyze", help="Run analysis and export all outputs")
    p_analyze.add_argument("--source", choices=["csv", "sqlite", "db"], required=True)
    p_analyze.add_argument("--csv", nargs="*", help="CSV file paths (for --source csv)")
    p_analyze.add_argument("--sqlite", help="SQLite DB path (for --source sqlite)")
    p_analyze.add_argument("--db-type", choices=["mysql", "postgres", "sqlserver"], help="DB type for --source db")
    p_analyze.add_argument("--host", help="DB host for --source db")
    p_analyze.add_argument("--port", type=int, help="DB port for --source db")
    p_analyze.add_argument("--database", help="DB name for --source db")
    p_analyze.add_argument("--username", help="DB username for --source db")
    p_analyze.add_argument("--password", default="", help="DB password for --source db")
    p_analyze.add_argument("--driver", default="ODBC Driver 17 for SQL Server", help="ODBC driver for SQL Server")
    p_analyze.add_argument("--profile-limit", type=int, default=25000)
    p_analyze.add_argument("--erd-view", choices=["full", "keys"], default="full")
    p_analyze.add_argument("--erd-layout", choices=["LR", "TB"], default="LR")
    p_analyze.add_argument("--out-dir", default="outputs")
    p_analyze.add_argument("--ai-brief", action="store_true", help="Generate AI executive brief")
    p_analyze.add_argument("--model", default="", help="Ollama model name override")
    p_analyze.add_argument("--ollama-endpoint", default="http://localhost:11434")
    p_analyze.add_argument("--commit-audit", action="store_true")
    p_analyze.add_argument("--actor", default="HackathonTeam")
    p_analyze.set_defaults(func=cmd_analyze)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
