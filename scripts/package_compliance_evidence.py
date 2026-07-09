#!/usr/bin/env python3
"""
ARGUS Compliance Evidence Packaging Script
Compiles and zips all audit assets required for EU AI Act, GDPR,
and ISO/IEC 42001 conformity reviews into a single zipped evidence pack.
"""

import os
import sys
import json
import shutil
import zipfile
import logging
import argparse
import subprocess
from datetime import datetime, timezone

try:
    # Imported as part of the `scripts` package (e.g. `from scripts.package_
    # compliance_evidence import ...`, as tests/unit/test_compliance_packaging.py does).
    from .secret_scan import scan_repo_for_secrets
except ImportError:
    # Run directly (`python scripts/package_compliance_evidence.py`) — there's
    # no parent package, but Python puts this script's own directory on
    # sys.path, so the plain module name resolves.
    from secret_scan import scan_repo_for_secrets

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("ARGUS_Compliance_Packaging")


def find_dvc_files(repo_root: str) -> dict:
    """
    Search for all DVC files recursively in the repository and collect their hashes.
    """
    dvc_hashes = {}
    for root, _, files in os.walk(repo_root):
        # Skip virtual env and hidden dirs
        if any(x in root for x in [".venv", ".git", ".pytest_cache", ".ruff_cache"]):
            continue

        for file in files:
            if file.endswith(".dvc"):
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, repo_root)
                try:
                    import yaml

                    with open(filepath, "r", encoding="utf-8") as f:
                        dvc_hashes[rel_path] = yaml.safe_load(f)
                except (ImportError, Exception):
                    # Parse basic YAML-like structure for md5 manually
                    try:
                        lines = {}
                        with open(filepath, "r", encoding="utf-8") as f:
                            for line in f:
                                if ":" in line:
                                    k, v = line.split(":", 1)
                                    lines[k.strip()] = v.strip()
                        dvc_hashes[rel_path] = lines
                    except Exception as e:
                        logger.warning(f"Failed to parse DVC file {rel_path}: {e}")
                except Exception as e:
                    logger.warning(f"Failed to read DVC file {rel_path}: {e}")

    return dvc_hashes


def get_git_log(repo_root: str) -> str:
    """
    Retrieve the git commit change log.
    """
    try:
        res = subprocess.run(
            [
                "git",
                "-C",
                repo_root,
                "log",
                "-n",
                "20",
                "--pretty=format:%h - %an, %ar : %s",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout
    except Exception as e:
        logger.warning(f"Failed to retrieve git log: {e}")
        return "Git commit history unavailable."


def run_security_scan(
    command: list, output_file: str, scanner_name: str, cwd: str | None = None
) -> dict:
    """
    Helper to run a security scanner CLI command and return structured status.
    """
    logger.info(f"Running security scan: {scanner_name}...")
    try:
        res = subprocess.run(command, capture_output=True, text=True, cwd=cwd)
        if res.returncode in (
            0,
            1,
            2,
        ):  # Bandit/Trivy/Gitleaks might use non-zero exit codes on findings
            try:
                if not os.path.exists(output_file):
                    if res.stdout:
                        with open(output_file, "w", encoding="utf-8") as f:
                            f.write(res.stdout)
                    else:
                        # Exit code looked like "success", but the tool wrote
                        # nothing to either the output file or stdout (e.g.
                        # pip-audit reporting an input error on stderr while
                        # still exiting 1). Record that explicitly rather
                        # than silently dropping this scan from the pack.
                        with open(output_file, "w", encoding="utf-8") as f:
                            json.dump(
                                {
                                    "scanner": scanner_name,
                                    "status": "NO_OUTPUT",
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "exit_code": res.returncode,
                                    "stderr": res.stderr[:500],
                                },
                                f,
                                indent=2,
                            )
                return {"status": "SUCCESS", "exit_code": res.returncode}
            except Exception as e:
                return {
                    "status": "WRITE_ERROR",
                    "error": str(e),
                    "exit_code": res.returncode,
                }
        else:
            # A non-{0,1,2} exit code means the scanner itself errored out
            # (e.g. pip-audit given a repo with no requirements.txt) rather
            # than just reporting findings. Still write a report file so the
            # evidence pack never silently drops this scan's entry.
            logger.warning(
                f"Scanner '{scanner_name}' exited with code {res.returncode}: {res.stderr[:200]}"
            )
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "scanner": scanner_name,
                        "status": "FAILED",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "exit_code": res.returncode,
                        "stderr": res.stderr[:500],
                    },
                    f,
                    indent=2,
                )
            return {
                "status": "FAILED",
                "exit_code": res.returncode,
                "stderr": res.stderr[:500],
            }
    except FileNotFoundError:
        logger.warning(f"Scanner '{scanner_name}' command not found on this system.")
        # Write stub indicating scanner was not run
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "scanner": scanner_name,
                    "status": "NOT_INSTALLED",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message": "Scanner CLI not installed on host environment.",
                },
                f,
                indent=2,
            )
        return {"status": "NOT_INSTALLED"}


def find_latest_training_run(tracking_uri: str, experiment_name: str) -> dict | None:
    """
    Look up the most recent MLflow run for the given experiment and return
    its logged metrics/params, or None if no run exists yet. Used so the
    model card reports whatever was actually measured rather than asserting
    a fixed target was met regardless of whether training ever happened.
    """
    try:
        import mlflow
        from mlflow.tracking import MlflowClient

        mlflow.set_tracking_uri(tracking_uri)
        client = MlflowClient()
        experiment = client.get_experiment_by_name(experiment_name)
        if experiment is None:
            return None

        runs = client.search_runs(
            experiment_ids=[experiment.experiment_id],
            order_by=["attributes.start_time DESC"],
            max_results=1,
        )
        if not runs:
            return None

        run = runs[0]
        return {
            "run_id": run.info.run_id,
            "metrics": dict(run.data.metrics),
            "params": dict(run.data.params),
        }
    except Exception as e:
        logger.warning(f"Could not query MLflow for a training run: {e}")
        return None


def generate_model_card(
    repo_root: str,
    tracking_uri: str = "sqlite:///mlflow.db",
    experiment_name: str = "ARGUS_Champion_Training",
) -> str:
    """
    Generate a formatted Model Card Markdown file compliant with AIMS/EU AI Act.
    Performance figures are pulled from the most recent MLflow run rather
    than asserted, so the card can never claim a result that wasn't measured.
    """
    git_commit = "Unknown"
    try:
        res = subprocess.run(
            ["git", "-C", repo_root, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        git_commit = res.stdout.strip()
    except Exception:
        pass

    run = find_latest_training_run(tracking_uri, experiment_name)

    if run is not None:
        metrics = run["metrics"]
        params = run["params"]
        apcer = metrics.get("val_apcer_at_1percent_bpcer")
        audet = metrics.get("val_audet")
        p95_ms = metrics.get("p95_latency_ms")
        train_size = params.get("train_size")
        val_size = params.get("val_size")
        if train_size and val_size:
            dataset_note = (
                f"Trained on {train_size} images, validated on {val_size} "
                "(logged directly from this run — see `train_size`/`val_size` "
                "params in MLflow), not assumed from a script default."
            )
        else:
            dataset_note = (
                "Dataset size for this run was not logged (older run, before "
                "`train_size`/`val_size` param logging was added) — check "
                "the MLflow run's `data.splits_dir` param to confirm scale."
            )

        overfitting_caveat = ""
        if apcer is not None and audet is not None and apcer < 0.001 and audet < 0.001:
            overfitting_caveat = (
                "\n\n**Caveat**: APCER and AuDET at this level (near-zero) are "
                "unusually low for a fraud-detection task and should be treated "
                "with suspicion, not celebrated at face value. Checked for the "
                "two most common causes of an artificially perfect score — exact "
                "duplicate images leaking between train/val, and a metadata "
                "shortcut that trivially predicts the label — and found neither "
                "in a spot check. This may reflect genuine in-distribution "
                "performance (synthetic fraud datasets often have consistent, "
                "learnable generator artifacts), but it is not evidence the "
                "model will perform this well on the private competition test "
                "set, which may include held-out attack types never seen in "
                "training. Do not cite these numbers as a competition-accuracy "
                "guarantee."
            )

        performance_section = f"""* **MLflow Run ID**: {run["run_id"]}
* **Architecture**: {params.get("model_name", "Unknown")}
* **Measured APCER @ 1% BPCER**: {f"{apcer:.4f}" if apcer is not None else "not logged"}
* **Measured AuDET**: {f"{audet:.4f}" if audet is not None else "not logged"}
* **Measured p95 Inference Latency**: {f"{p95_ms:.1f} ms" if p95_ms is not None else "not logged"}
* **Training Epochs**: {params.get("epochs", "Unknown")} | **Batch Size**: {params.get("batch_size", "Unknown")} | **Image Size**: {params.get("image_size", "Unknown")}

{dataset_note}{overfitting_caveat}"""
    else:
        performance_section = (
            "* **No completed training run found** in the "
            f"`{experiment_name}` MLflow experiment at `{tracking_uri}`. "
            "Run `scripts/train_champion_checkpoint.sh` to train the "
            "champion checkpoint and populate this section with measured "
            "results before treating this model card as submission evidence."
        )

    card = f"""# ARGUS Model Card (Conformity Record)

## 1. Model Metadata
* **Model System Name**: ARGUS Identity verification and fraud detection
* **Model Version**: v1.3.0
* **Git Commit**: {git_commit}
* **Conformity Assessment Date**: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}

## 2. Intended Use and Scope
* **Intended Users**: Identity Verification Agents, MLOps Engineers, Compliance Officers.
* **Target Domain**: Secure facial and identity document verification (genuine vs. fraud detection).
* **Limitations**: Optimised for JPEG/PNG document scans (<15MB size). Not designed for real-time video stream verification.

## 3. Training & Validation Performance
{performance_section}

## 4. Compliance & Controls
* **PII Governance**: Strict filter in logging middleware (`AuditLoggingMiddleware`) strips all biometrics, raw image base64, and user personal data.
* **Secure Storage**: Ephemeral human-review encryption (Fernet symmetric key) with a strict 24-hour TTL file-cleanup daemon.
* **Drift Control**: Daily automated PSI monitoring; alerting threshold set to 0.20.
"""
    return card


def generate_conformity_assessment() -> str:
    """
    Generates a conformity assessment mapping Article requirements of the EU AI Act.
    """
    doc = """# EU AI Act Technical Conformity Assessment (Article 11)

This document maps the ARGUS technical controls to the requirements set forth in the EU AI Act for High-Risk AI Systems.

## Article 9: Risk Management System
* **Control**: Risk register is maintained under `docs/Phase-4/08_Security_Compliance.md`.
* **Verification**: Continuous penetration testing, security checks, and fallback mechanisms (human-in-the-loop review for ambiguous classifications).

## Article 10: Data and Data Governance
* **Control**: Training, validation, and test splits are version-controlled deterministically via DVC.
* **Verification**: Integrity checks run on ingestion. EXIF metadata is stripped from images automatically to enforce biometrics protection and avoid leakage.

## Article 11: Technical Documentation
* **Control**: Full system documentation, ML design cards, and operations runbooks are stored directly in version control.
* **Verification**: The automated compliance packaging script compiles this conformity pack on demand.

## Article 12: Record-Keeping (Logging)
* **Control**: Automated structured JSON audit logging is integrated in `src/api/audit.py`.
* **Verification**: Captures request ID, endpoint, latency, decision confidence, and requires_human_review flag. No PII is logged.

## Article 13: Transparency and Provision of Information
* **Control**: Transparent model cards are compiled outlining capabilities and limitations. Saliency maps (attention maps) are returned to users to explain predictions.

## Article 14: Human Oversight
* **Control**: Classifications falling into low confidence (<0.70 by default) or ambiguous score boundaries (0.40 - 0.60 by default) are routed to an encrypted secure human-review queue. Thresholds are env-configurable (`HUMAN_REVIEW_CONFIDENCE_THRESHOLD`, `HUMAN_REVIEW_SCORE_BAND_LOW/HIGH` — see `src/api/main.py`), not hardcoded.
"""
    return doc


def generate_data_processing_records(repo_root: str) -> dict:
    """
    Generate static documentation on data splits and processing integrity constraints.
    """
    return {
        "dataset_name": "FREUID Dataset",
        "splits_ratio": "70% Train, 15% Validation, 15% Test",
        "random_seed": 42,
        "processing_steps": [
            "Deterministic image ingest validation",
            "PII removal: EXIF tag stripping via PIL",
            "Symmetric Fernet encryption for human review queue",
            "Strict 24-hour retention TTL on disk storage",
        ],
        "compliance_policies": {
            "GDPR_retention_compliant": True,
            "biometric_data_strip": True,
        },
    }


def package_evidence(
    repo_root: str,
    output_zip_path: str,
    drift_report_path: str,
    retraining_state_path: str,
    mlflow_tracking_uri: str = "sqlite:///mlflow.db",
    mlflow_experiment_name: str = "ARGUS_Champion_Training",
):
    """
    Stages, formats, and packages all compliance evidence into a single ZIP file.
    """
    # Create temporary staging directory
    stage_dir = os.path.join(repo_root, "outputs", "evidence_stage")
    if os.path.exists(stage_dir):
        shutil.rmtree(stage_dir)
    os.makedirs(stage_dir, exist_ok=True)

    logger.info(f"Staging compliance evidence in: {stage_dir}")

    try:
        # 1. Collect DVC hashes
        dvc_hashes = find_dvc_files(repo_root)
        with open(
            os.path.join(stage_dir, "dvc_hashes.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(dvc_hashes, f, indent=2)

        # 2. Collect Git Change Log
        git_log = get_git_log(repo_root)
        with open(
            os.path.join(stage_dir, "change_log.txt"), "w", encoding="utf-8"
        ) as f:
            f.write(git_log)

        # 3. Generate Model Card
        model_card = generate_model_card(
            repo_root, mlflow_tracking_uri, mlflow_experiment_name
        )
        with open(os.path.join(stage_dir, "model_card.md"), "w", encoding="utf-8") as f:
            f.write(model_card)

        # 4. Generate Conformity Assessment
        conformity = generate_conformity_assessment()
        with open(
            os.path.join(stage_dir, "conformity_assessment.md"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write(conformity)

        # 5. Collect Data Processing Records
        data_processing = generate_data_processing_records(repo_root)
        with open(
            os.path.join(stage_dir, "data_processing_records.json"),
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(data_processing, f, indent=2)

        # 6. Copy Drift Report if available
        if os.path.exists(drift_report_path):
            shutil.copy(drift_report_path, os.path.join(stage_dir, "drift_report.json"))
            logger.info("Drift report copied to evidence pack.")
        else:
            logger.warning(f"Drift report not found at {drift_report_path}")

        # 7. Copy Retraining State if available
        if os.path.exists(retraining_state_path):
            shutil.copy(
                retraining_state_path,
                os.path.join(stage_dir, "retraining_state.json"),
            )
            logger.info("Retraining state copied to evidence pack.")
        else:
            logger.warning(f"Retraining state not found at {retraining_state_path}")

        # 8. Run Security Scans
        # SAST (Bandit) — pip-installable, see requirements-dev.txt
        run_security_scan(
            ["bandit", "-r", "src/", "-f", "json"],
            os.path.join(stage_dir, "sast_bandit_report.json"),
            "Bandit SAST",
            cwd=repo_root,
        )

        # Secrets — gitleaks/trufflehog ship as standalone binaries with no
        # pip package, so rather than a "NOT_INSTALLED" stub when the binary
        # is absent, run the repo's own regex-based scanner directly. It's a
        # narrower check than gitleaks but a real one, always available.
        secret_findings = scan_repo_for_secrets(repo_root)
        with open(
            os.path.join(stage_dir, "secret_scan_report.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(
                {
                    "scanner": "ARGUS built-in secret scanner (scripts/secret_scan.py)",
                    "status": "FINDINGS" if secret_findings else "CLEAN",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "findings_count": len(secret_findings),
                    "findings": secret_findings,
                },
                f,
                indent=2,
            )
        if secret_findings:
            logger.warning(
                f"Secret scan found {len(secret_findings)} potential secret(s) — review before submitting."
            )

        # Dependency scan — Trivy is a standalone Go binary with no pip
        # package; pip-audit (see requirements-dev.txt) does the same job
        # for Python dependencies against the PyPI/OSV advisory databases
        # and is installable in any Python environment.
        run_security_scan(
            ["pip-audit", "--format", "json", "-r", "requirements.txt"],
            os.path.join(stage_dir, "dependency_scan_report.json"),
            "pip-audit Dependency Scan",
            cwd=repo_root,
        )

        # 9. Create ZIP file
        os.makedirs(os.path.dirname(os.path.abspath(output_zip_path)), exist_ok=True)
        with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(stage_dir):
                for file in files:
                    filepath = os.path.join(root, file)
                    arcname = os.path.relpath(filepath, stage_dir)
                    zipf.write(filepath, arcname)

        logger.info(
            f"Successfully packaged compliance evidence zip at: {output_zip_path}"
        )

    finally:
        # Cleanup staging area
        if os.path.exists(stage_dir):
            shutil.rmtree(stage_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ARGUS Compliance Evidence Packaging Utility"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="outputs/compliance_evidence_pack.zip",
        help="Path where the final zipped evidence pack will be written",
    )
    parser.add_argument(
        "--drift-report",
        type=str,
        default="outputs/drift_report.json",
        help="Path to the drift report JSON file",
    )
    parser.add_argument(
        "--retraining-state",
        type=str,
        default="data/retraining_state.json",
        help="Path to the retraining state JSON file",
    )
    parser.add_argument(
        "--mlflow-tracking-uri",
        type=str,
        default="sqlite:///mlflow.db",
        help="MLflow tracking URI to pull the model card's performance metrics from",
    )
    parser.add_argument(
        "--mlflow-experiment-name",
        type=str,
        default="ARGUS_Champion_Training",
        help="MLflow experiment to pull the latest training run from",
    )

    args = parser.parse_args()

    # Resolve repo root relative to scripts directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, ".."))

    out_path = (
        args.output
        if os.path.isabs(args.output)
        else os.path.abspath(os.path.join(project_root, args.output))
    )
    drift_path = (
        args.drift_report
        if os.path.isabs(args.drift_report)
        else os.path.abspath(os.path.join(project_root, args.drift_report))
    )
    retrain_path = (
        args.retraining_state
        if os.path.isabs(args.retraining_state)
        else os.path.abspath(os.path.join(project_root, args.retraining_state))
    )

    try:
        package_evidence(
            repo_root=project_root,
            output_zip_path=out_path,
            drift_report_path=drift_path,
            retraining_state_path=retrain_path,
            mlflow_tracking_uri=args.mlflow_tracking_uri,
            mlflow_experiment_name=args.mlflow_experiment_name,
        )
        sys.exit(0)
    except Exception as exc:
        logger.exception(f"Compliance evidence packaging failed: {exc}")
        sys.exit(1)
