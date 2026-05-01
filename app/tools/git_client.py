from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class GitClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._platform = settings.git.platform
        self._base_url = settings.git.base_url.rstrip("/")
        self._token = settings.git.access_token

    def _headers(self) -> dict[str, str]:
        if self._platform == "gitlab":
            return {"PRIVATE-TOKEN": self._token}
        return {
            "Authorization": f"token {self._token}",
            "Accept": "application/vnd.github.v3+json",
        }

    async def get_pr_diff(
        self,
        repo_url: str,
        pr_id: int,
        branch: Optional[str] = None,
    ) -> dict[str, Any]:
        if self._platform == "gitlab":
            return await self._gitlab_pr_diff(repo_url, pr_id)
        return await self._github_pr_diff(repo_url, pr_id)

    async def _gitlab_pr_diff(
        self, repo_url: str, pr_id: int
    ) -> dict[str, Any]:
        project_path = repo_url.replace(f"{self._base_url}/", "")
        encoded_path = project_path.replace("/", "%2F")
        url = f"{self._base_url}/api/v4/projects/{encoded_path}/merge_requests/{pr_id}/changes"

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()

        changed_files = []
        for change in data.get("changes", []):
            changed_files.append({
                "old_path": change.get("old_path", ""),
                "new_path": change.get("new_path", ""),
                "diff": change.get("diff", ""),
                "new_file": change.get("new_file", False),
                "deleted_file": change.get("deleted_file", False),
                "renamed_file": change.get("renamed_file", False),
            })

        return {
            "pr_id": pr_id,
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "source_branch": data.get("source_branch", ""),
            "target_branch": data.get("target_branch", ""),
            "changed_files": changed_files,
        }

    async def _github_pr_diff(
        self, repo_url: str, pr_id: int
    ) -> dict[str, Any]:
        repo_path = repo_url.replace("https://github.com/", "")
        url = f"https://api.github.com/repos/{repo_path}/pulls/{pr_id}"

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()

        files_url = f"https://api.github.com/repos/{repo_path}/pulls/{pr_id}/files"
        async with httpx.AsyncClient(timeout=60) as client:
            files_resp = await client.get(files_url, headers=self._headers())
            files_resp.raise_for_status()
            files_data = files_resp.json()

        changed_files = []
        for f in files_data:
            changed_files.append({
                "old_path": f.get("filename", ""),
                "new_path": f.get("filename", ""),
                "diff": f.get("patch", ""),
                "new_file": f.get("status") == "added",
                "deleted_file": f.get("status") == "removed",
                "renamed_file": f.get("status") == "renamed",
            })

        return {
            "pr_id": pr_id,
            "title": data.get("title", ""),
            "description": data.get("body", ""),
            "source_branch": data.get("head", {}).get("ref", ""),
            "target_branch": data.get("base", {}).get("ref", ""),
            "changed_files": changed_files,
        }

    async def get_file_content(
        self,
        repo_url: str,
        file_path: str,
        branch: str = "main",
    ) -> Optional[str]:
        if self._platform == "gitlab":
            return await self._gitlab_file_content(repo_url, file_path, branch)
        return await self._github_file_content(repo_url, file_path, branch)

    async def _gitlab_file_content(
        self, repo_url: str, file_path: str, branch: str
    ) -> Optional[str]:
        project_path = repo_url.replace(f"{self._base_url}/", "")
        encoded_path = project_path.replace("/", "%2F")
        import urllib.parse
        encoded_file = urllib.parse.quote(file_path, safe="")
        url = (
            f"{self._base_url}/api/v4/projects/{encoded_path}"
            f"/repository/files/{encoded_file}/raw?ref={branch}"
        )

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(url, headers=self._headers())
                resp.raise_for_status()
                return resp.text
            except httpx.HTTPStatusError:
                logger.warning(f"File not found: {file_path} in {repo_url}")
                return None

    async def _github_file_content(
        self, repo_url: str, file_path: str, branch: str
    ) -> Optional[str]:
        repo_path = repo_url.replace("https://github.com/", "")
        url = (
            f"https://api.github.com/repos/{repo_path}"
            f"/contents/{file_path}?ref={branch}"
        )

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(url, headers=self._headers())
                resp.raise_for_status()
                import base64
                data = resp.json()
                return base64.b64decode(data["content"]).decode("utf-8")
            except httpx.HTTPStatusError:
                logger.warning(f"File not found: {file_path} in {repo_url}")
                return None

    async def post_pr_comment(
        self,
        repo_url: str,
        pr_id: int,
        comment: str,
    ) -> bool:
        if self._platform == "gitlab":
            return await self._gitlab_post_comment(repo_url, pr_id, comment)
        return await self._github_post_comment(repo_url, pr_id, comment)

    async def _gitlab_post_comment(
        self, repo_url: str, pr_id: int, comment: str
    ) -> bool:
        project_path = repo_url.replace(f"{self._base_url}/", "")
        encoded_path = project_path.replace("/", "%2F")
        url = (
            f"{self._base_url}/api/v4/projects/{encoded_path}"
            f"/merge_requests/{pr_id}/notes"
        )

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(
                    url,
                    headers=self._headers(),
                    json={"body": comment},
                )
                resp.raise_for_status()
                return True
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to post comment: {e}")
                return False

    async def _github_post_comment(
        self, repo_url: str, pr_id: int, comment: str
    ) -> bool:
        repo_path = repo_url.replace("https://github.com/", "")
        url = (
            f"https://api.github.com/repos/{repo_path}"
            f"/issues/{pr_id}/comments"
        )

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(
                    url,
                    headers=self._headers(),
                    json={"body": comment},
                )
                resp.raise_for_status()
                return True
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to post comment: {e}")
                return False
