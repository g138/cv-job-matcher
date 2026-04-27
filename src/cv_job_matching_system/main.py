#!/usr/bin/env python
import os
import sys

from cv_job_matching_system.crew import CvJobMatchingSystemCrew


def _read_cv(file_path: str) -> str:
    """Read CV content from a PDF or plain-text file."""
    if file_path.lower().endswith(".pdf"):
        try:
            import fitz  # pymupdf
            doc = fitz.open(file_path)
            return "\n".join(page.get_text() for page in doc).strip()
        except Exception as exc:
            print(f"  Warning: PDF read failed ({exc}). Trying plain text fallback.")
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read().strip()


def _prompt(message: str, default: str = "") -> str:
    """Prompt the user for input, showing the default value if provided."""
    if default:
        value = input(f"{message} [{default}]: ").strip()
        return value if value else default
    value = input(f"{message}: ").strip()
    return value


def _check_env():
    """Fail fast if required API keys are missing."""
    missing = []
    if not os.getenv("GROQ_API_KEY"):
        missing.append("GROQ_API_KEY  — get free key at https://console.groq.com")
    if not os.getenv("SERPER_API_KEY"):
        missing.append("SERPER_API_KEY — get free key at https://serper.dev")
    if missing:
        print("\nERROR: Missing required environment variables in your .env file:\n")
        for m in missing:
            print(f"  • {m}")
        print("\nAdd them to your .env file and try again.\n")
        sys.exit(1)


def run():
    """
    Interactively collect inputs from the user and run the job search crew.
    """
    _check_env()
    print("\n" + "=" * 60)
    print("  CV Job Matching System — AI-Powered Job Search")
    print("=" * 60)
    print(
        "\nThis system will analyse your CV, search LinkedIn, Indeed,\n"
        "and the web for matching jobs, then find recruiter contacts.\n"
    )

    cv_file_path = _prompt("Path to your CV file (PDF or text)")
    cv_file_path = cv_file_path.strip("'\"")
    while not cv_file_path or not os.path.exists(cv_file_path):
        if not cv_file_path:
            print("  CV file path is required.")
        else:
            print(f"  File not found: {cv_file_path!r}")
            print("  Tip: do NOT wrap the path in quotes — just paste it as-is.")
        cv_file_path = _prompt("Path to your CV file (PDF or text)").strip("'\"")

    candidate_name = _prompt("Your full name")
    while not candidate_name:
        print("  Name is required.")
        candidate_name = _prompt("Your full name")

    location = _prompt(
        "Preferred job location (e.g. 'London, UK', 'New York, USA', 'Remote')"
    )
    while not location:
        print("  Location is required.")
        location = _prompt(
            "Preferred job location (e.g. 'London, UK', 'New York, USA', 'Remote')"
        )

    print(f"\nReading CV from {cv_file_path} ...")
    cv_content = _read_cv(cv_file_path)
    if not cv_content:
        print("  ERROR: Could not read any text from the CV file. Check the file and try again.")
        sys.exit(1)
    print(f"  CV loaded ({len(cv_content)} characters).")
    print(f"\nStarting job search for {candidate_name} — {location} ...\n")

    inputs = {
        "candidate_name": candidate_name,
        "cv_file_path": cv_file_path,
        "cv_content": cv_content,
        "location": location,
    }

    result = CvJobMatchingSystemCrew().crew().kickoff(inputs=inputs)

    print("\n" + "=" * 60)
    print("  Job Search Complete!")
    print("=" * 60)
    print("\nFull report saved to: output/job_search_report.md\n")
    print(result.raw)
    return result


def train():
    """Train the crew for a given number of iterations."""
    inputs = {
        "candidate_name": "Sample Candidate",
        "cv_file_path": "sample_cv.txt",
        "location": "London, UK",
    }
    try:
        CvJobMatchingSystemCrew().crew().train(
            n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs
        )
    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")


def replay():
    """Replay the crew execution from a specific task."""
    try:
        CvJobMatchingSystemCrew().crew().replay(task_id=sys.argv[1])
    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")


def test():
    """Test the crew execution and return the results."""
    inputs = {
        "candidate_name": "Test Candidate",
        "cv_file_path": "sample_cv.txt",
        "location": "London, UK",
    }
    try:
        CvJobMatchingSystemCrew().crew().test(
            n_iterations=int(sys.argv[1]),
            openai_model_name=sys.argv[2],
            inputs=inputs,
        )
    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")


def run_with_trigger():
    """Entry point for programmatic or scheduled triggers (same as run but non-interactive)."""
    cv_file_path = os.getenv("CV_FILE_PATH", "cv.pdf")
    inputs = {
        "candidate_name": os.getenv("CANDIDATE_NAME", "Candidate"),
        "cv_file_path": cv_file_path,
        "cv_content": _read_cv(cv_file_path),
        "location": os.getenv("JOB_LOCATION", "Remote"),
    }
    result = CvJobMatchingSystemCrew().crew().kickoff(inputs=inputs)
    print(result.raw)
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        run()
        sys.exit(0)

    command = sys.argv[1]
    if command == "run":
        run()
    elif command == "train":
        train()
    elif command == "replay":
        replay()
    elif command == "test":
        test()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
