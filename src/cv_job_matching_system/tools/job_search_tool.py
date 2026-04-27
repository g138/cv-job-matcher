import os
import json
from typing import Type

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class JobSearchInput(BaseModel):
    job_titles: str = Field(
        ...,
        description="Comma-separated list of job titles to search for (e.g. 'Software Engineer, Backend Developer')",
    )
    location: str = Field(
        ...,
        description="Job location to search in (e.g. 'London, UK', 'New York, USA', 'Remote')",
    )
    key_skills: str = Field(
        default="",
        description="Comma-separated key skills to refine the search (e.g. 'Python, AWS, Docker')",
    )


class JobSearchTool(BaseTool):
    name: str = "job_search"
    description: str = (
        "Searches for job openings on LinkedIn Jobs, Indeed, and the web. "
        "Provide job titles, location, and key skills to find relevant positions. "
        "Returns a list of job listings with title, company, URL, and description."
    )
    args_schema: Type[BaseModel] = JobSearchInput

    def _run(self, job_titles: str, location: str, key_skills: str = "") -> str:
        api_key = os.getenv("SERPER_API_KEY")
        if not api_key:
            return "ERROR: SERPER_API_KEY environment variable is not set. Cannot perform job search."

        titles = [t.strip() for t in job_titles.split(",") if t.strip()][:3]
        all_results: list[dict] = []

        for title in titles:
            queries = [
                f'site:linkedin.com/jobs "{title}" "{location}"',
                f'site:indeed.com "{title}" "{location}" apply',
                f'"{title}" job opening "{location}" -site:glassdoor.com',
            ]
            for query in queries:
                hits = self._serper_search(api_key, query, num=5)
                for hit in hits:
                    hit["search_title"] = title
                    hit["platform"] = self._detect_platform(hit.get("link", ""))
                all_results.extend(hits)

        if not all_results:
            return (
                f"No job listings found for '{job_titles}' in '{location}'. "
                "Try broader job titles or a different location."
            )

        seen_urls: set[str] = set()
        unique_results: list[dict] = []
        for r in all_results:
            url = r.get("link", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(r)

        output_lines = [
            f"Found {len(unique_results)} job listings for '{job_titles}' in '{location}':\n"
        ]
        for i, job in enumerate(unique_results[:20], 1):
            output_lines.append(
                f"{i}. [{job.get('platform', 'Web')}] {job.get('title', 'Unknown Role')}"
            )
            output_lines.append(f"   URL: {job.get('link', 'N/A')}")
            snippet = job.get("snippet", "")
            if snippet:
                output_lines.append(f"   Details: {snippet[:200]}")
            output_lines.append("")

        return "\n".join(output_lines)

    def _serper_search(self, api_key: str, query: str, num: int = 5) -> list[dict]:
        try:
            response = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "num": num},
                timeout=15,
            )
            response.raise_for_status()
            return response.json().get("organic", [])
        except Exception as exc:
            return []

    def _detect_platform(self, url: str) -> str:
        url_lower = url.lower()
        if "linkedin.com" in url_lower:
            return "LinkedIn"
        if "indeed.com" in url_lower:
            return "Indeed"
        if "glassdoor.com" in url_lower:
            return "Glassdoor"
        if "reed.co.uk" in url_lower:
            return "Reed"
        if "totaljobs.com" in url_lower:
            return "TotalJobs"
        return "Web"
