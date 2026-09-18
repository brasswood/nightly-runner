#!/usr/bin/env python3

from typing import Mapping
import json
import urllib.error
import urllib.parse
import urllib.request


NORTHFLANK_API_URL = "https://api.northflank.com/v1"


class NorthflankError(RuntimeError):
    pass


def parse_job_spec(spec: str) -> tuple[str, str]:
    project, separator, job = spec.partition("/")
    if not separator or not project or not job or "/" in job:
        raise NorthflankError(
            f"Invalid Northflank job spec {spec!r}; expected project-id/job-id"
        )
    return project, job


class Runner:
    def __init__(self, secrets: Mapping[str, Mapping[str, str]], spec: str) -> None:
        project, job = parse_job_spec(spec)
        if "northflank" not in secrets:
            raise NorthflankError("Missing token for Northflank")
        token = secrets["northflank"].get("token")
        if not token:
            raise NorthflankError("Missing token for Northflank")

        self.url = (
            f"{NORTHFLANK_API_URL}/projects/{urllib.parse.quote(project, safe='')}"
            f"/jobs/{urllib.parse.quote(job, safe='')}/runs"
        )
        self.token = token

    def start_job(
        self,
        repo: str,
        branch: str,
        commit: str,
        *,
        timeout: str | None,
        ppa: str | None,
        apt: str | None,
    ) -> str:
        environment = {
            "NIGHTLIES_REPO": repo,
            "NIGHTLIES_BRANCH": branch,
            "NIGHTLIES_COMMIT": commit,
        }
        for name, value in (
            ("TIMEOUT", timeout),
            ("PPA", ppa),
            ("APT", apt),
        ):
            if value:
                environment["NIGHTLIES_" + name] = value

        request = urllib.request.Request(
            self.url,
            data=json.dumps({"runtimeEnvironment": environment}).encode("utf-8"),
            method="POST",
        )
        request.add_header("Content-Type", "application/json")
        request.add_header("Authorization", f"Bearer {self.token}")

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = response.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise NorthflankError(f"Northflank API returned HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise NorthflankError(f"Northflank API request failed: {e.reason}") from e

        try:
            result = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise NorthflankError(f"Northflank API returned invalid JSON: {e}") from e
        if not isinstance(result, dict) or not isinstance(result.get("data"), dict):
            raise NorthflankError(f"Northflank API returned an invalid response: {result!r}")
        run_name = result["data"].get("runName")
        if not isinstance(run_name, str):
            raise NorthflankError(f"Northflank API returned an invalid response: {result!r}")
        return run_name
