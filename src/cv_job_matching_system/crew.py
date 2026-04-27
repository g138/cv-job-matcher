from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai_tools import ScrapeWebsiteTool
from typing import List

from cv_job_matching_system.tools.job_search_tool import JobSearchTool
from cv_job_matching_system.tools.recruiter_finder_tool import RecruiterFinderTool


_DEFAULT_LLM = LLM(model="groq/llama-3.3-70b-versatile")


@CrewBase
class CvJobMatchingSystemCrew:
    """CV Job Matching System — searches LinkedIn, Indeed & web for jobs and finds recruiter contacts."""

    agents: List[BaseAgent]
    tasks: List[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # ------------------------------------------------------------------
    # Agents
    # ------------------------------------------------------------------

    @agent
    def cv_analysis_specialist(self) -> Agent:
        return Agent(
            config=self.agents_config["cv_analysis_specialist"],  # type: ignore[index]
            tools=[],
            inject_date=True,
            allow_delegation=False,
            max_iter=10,
            verbose=True,
            llm=_DEFAULT_LLM,
        )

    @agent
    def job_search_specialist(self) -> Agent:
        return Agent(
            config=self.agents_config["job_search_specialist"],  # type: ignore[index]
            tools=[
                JobSearchTool(),
                ScrapeWebsiteTool(),
            ],
            inject_date=True,
            allow_delegation=False,
            max_iter=30,
            verbose=True,
            llm=_DEFAULT_LLM,
        )

    @agent
    def recruiter_contact_finder(self) -> Agent:
        return Agent(
            config=self.agents_config["recruiter_contact_finder"],  # type: ignore[index]
            tools=[RecruiterFinderTool()],
            inject_date=True,
            allow_delegation=False,
            max_iter=30,
            verbose=True,
            llm=_DEFAULT_LLM,
        )

    @agent
    def job_report_compiler(self) -> Agent:
        return Agent(
            config=self.agents_config["job_report_compiler"],  # type: ignore[index]
            tools=[],
            inject_date=True,
            allow_delegation=False,
            max_iter=15,
            verbose=True,
            llm=_DEFAULT_LLM,
        )

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    @task
    def analyze_cv(self) -> Task:
        return Task(
            config=self.tasks_config["analyze_cv"],  # type: ignore[index]
            markdown=True,
        )

    @task
    def search_jobs(self) -> Task:
        return Task(
            config=self.tasks_config["search_jobs"],  # type: ignore[index]
            markdown=True,
        )

    @task
    def find_recruiter_contacts(self) -> Task:
        return Task(
            config=self.tasks_config["find_recruiter_contacts"],  # type: ignore[index]
            markdown=True,
        )

    @task
    def generate_job_search_report(self) -> Task:
        return Task(
            config=self.tasks_config["generate_job_search_report"],  # type: ignore[index]
            markdown=True,
        )

    # ------------------------------------------------------------------
    # Crew
    # ------------------------------------------------------------------

    @crew
    def crew(self) -> Crew:
        """Creates the CV Job Matching crew."""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            chat_llm=_DEFAULT_LLM,
        )
