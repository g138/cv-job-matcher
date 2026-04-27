import os
import re
from typing import Type

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class RecruiterFinderInput(BaseModel):
    company_name: str = Field(
        ...,
        description="Name of the company to find recruiter contact for (e.g. 'Google', 'Accenture')",
    )
    job_title: str = Field(
        ...,
        description="Job title the recruiter is hiring for (e.g. 'Software Engineer')",
    )


class RecruiterFinderTool(BaseTool):
    name: str = "recruiter_finder"
    description: str = (
        "Finds recruiter email addresses, LinkedIn profiles, and HR contact information "
        "for a given company and job role. Uses web search to locate active recruiters "
        "who are hiring for the specified position."
    )
    args_schema: Type[BaseModel] = RecruiterFinderInput

    _EMAIL_RE = re.compile(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    )

    def _run(self, company_name: str, job_title: str) -> str:
        api_key = os.getenv("SERPER_API_KEY")
        if not api_key:
            return "ERROR: SERPER_API_KEY environment variable is not set."

        queries = [
            f'"{company_name}" recruiter "{job_title}" site:linkedin.com/in',
            f'"{company_name}" talent acquisition "{job_title}" recruiter email',
            f'"{company_name}" HR recruiter hiring "{job_title}" contact',
            f'"{company_name}" careers contact email recruiter',
        ]

        all_results: list[dict] = []
        for query in queries:
            hits = self._serper_search(api_key, query, num=5)
            all_results.extend(hits)

        if not all_results:
            return (
                f"No recruiter contacts found for {company_name} ({job_title}). "
                "The company may not have public recruiter contact information available."
            )

        emails_found: set[str] = set()
        linkedin_profiles: list[str] = []
        contact_snippets: list[str] = []

        for result in all_results:
            snippet = result.get("snippet", "")
            link = result.get("link", "")
            title = result.get("title", "")

            for email in self._EMAIL_RE.findall(snippet + " " + title):
                if not any(skip in email for skip in ["example", "yourname", "noreply", "no-reply"]):
                    emails_found.add(email.lower())

            if "linkedin.com/in/" in link:
                linkedin_profiles.append(f"{title} — {link}")

            if snippet:
                contact_snippets.append(f"• {title}: {snippet[:180]}")

        output_lines = [
            f"Recruiter contacts for **{company_name}** (hiring: {job_title}):\n"
        ]

        if emails_found:
            output_lines.append("**Emails found:**")
            for email in sorted(emails_found)[:5]:
                output_lines.append(f"  - {email}")
            output_lines.append("")

        if linkedin_profiles:
            output_lines.append("**LinkedIn recruiter profiles:**")
            for profile in linkedin_profiles[:5]:
                output_lines.append(f"  - {profile}")
            output_lines.append("")

        if contact_snippets and not emails_found and not linkedin_profiles:
            output_lines.append("**Contact information found:**")
            for snippet in contact_snippets[:5]:
                output_lines.append(snippet)
            output_lines.append("")

        if not emails_found and not linkedin_profiles:
            output_lines.append(
                f"No direct email addresses found. "
                f"Try visiting {company_name}'s careers page or LinkedIn company page directly. "
                f"Common HR email patterns: careers@{company_name.lower().replace(' ', '')}.com, "
                f"talent@{company_name.lower().replace(' ', '')}.com"
            )

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
        except Exception:
            return []
