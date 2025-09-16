import base64
import logging
import os
import platform
import sys
from importlib.metadata import version
from typing import AsyncGenerator, Dict, Optional

import allure
import pytest
from browser_use import Agent, BrowserProfile, BrowserSession
from browser_use.llm import ChatOpenAI
from browser_use.utils import get_browser_use_version
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# Load environment variables from .env file
load_dotenv()


@pytest.fixture(scope="session")
def browser_version_info(browser_profile: BrowserProfile) -> Dict[str, str]:
    """
    Fixture to get Playwright and browser version info.
    """
    try:
        playwright_version = version("playwright")
        with sync_playwright() as p:
            browser_type_name = (
                browser_profile.channel.value if browser_profile.channel else "chromium"
            )
            browser = p[browser_type_name].launch()
            browser_version = browser.version
            browser.close()
        return {
            "playwright_version": playwright_version,
            "browser_version": browser_version,
        }
    except Exception as e:
        logging.warning(f"Could not determine Playwright/browser version: {e}")
        return {
            "playwright_version": "N/A",
            "browser_version": "N/A",
        }


@pytest.fixture(scope="session", autouse=True)
def environment_reporter(
    request: pytest.FixtureRequest,
    llm: ChatOpenAI,
    browser_profile: BrowserProfile,
    browser_version_info: Dict[str, str],
):
    """
    Fixture to write environment details to a properties file for reporting.
    This runs once per session and is automatically used.
    By default, this creates `environment.properties` for Allure.
    """
    allure_dir = request.config.getoption("--alluredir")
    if not allure_dir or not isinstance(allure_dir, str):
        return

    ENVIRONMENT_PROPERTIES_FILENAME = "environment.properties"
    properties_file = os.path.join(allure_dir, ENVIRONMENT_PROPERTIES_FILENAME)

    # Ensure the directory exists, with permission handling
    try:
        os.makedirs(allure_dir, exist_ok=True)
    except PermissionError:
        logging.error(f"Permission denied to create report directory: {allure_dir}")
        return  # Exit if we can't create the directory

    env_props = {
        "operating_system": f"{platform.system()} {platform.release()}",
        "python_version": sys.version.split(" ")[0],
        "browser_use_version": get_browser_use_version(),
        "playwright_version": browser_version_info["playwright_version"],
        "browser_type": (
            browser_profile.channel.value if browser_profile.channel else "chromium"
        ),
        "browser_version": browser_version_info["browser_version"],
        "headless_mode": str(browser_profile.headless),
        "llm_model": llm.model,
    }

    try:
        with open(properties_file, "w") as f:
            for key, value in env_props.items():
                f.write(f"{key}={value}\n")
    except IOError as e:
        logging.error(f"Failed to write environment properties file: {e}")


@pytest.fixture(scope="session")
def llm() -> ChatOpenAI:
    """Session-scoped fixture to initialize the language model."""
    return ChatOpenAI(model="gpt-4o")


@pytest.fixture(scope="session")
def browser_profile() -> BrowserProfile:
    """Session-scoped fixture for browser profile configuration."""
    headless_mode = os.getenv("HEADLESS", "True").lower() in ("true", "1", "t")
    return BrowserProfile(headless=headless_mode)


@pytest.fixture(scope="function")
async def browser_session(
    browser_profile: BrowserProfile,
) -> AsyncGenerator[BrowserSession, None]:
    """Function-scoped fixture to manage the browser session's lifecycle."""
    session = BrowserSession(browser_profile=browser_profile)
    yield session
    await session.close()


# --- Base Test Class for Agent-based Tests ---


class BaseAgentTest:
    """Base class for agent-based tests to reduce boilerplate."""

    BASE_URL = "https://discuss.google.dev/"

    async def validate_task(
        self,
        llm: ChatOpenAI,
        browser_session: BrowserSession,
        task_instruction: str,
        expected_substring: Optional[str] = None,
        ignore_case: bool = False,
    ) -> str:
        """
        Runs a task with the agent, prepends the BASE_URL, and performs common assertions.

        Args:
            llm: The language model instance.
            browser_session: The browser session instance.
            task_instruction: The specific instruction for the agent, without the "Go to URL" part.
            expected_substring: An optional string to assert is present in the agent's result.
            ignore_case: If True, the substring check will be case-insensitive.

        Returns:
            The final text result from the agent for any further custom assertions.
        """
        full_task = f"Go to {self.BASE_URL}, then {task_instruction}"

        result_text = await run_agent_task(full_task, llm, browser_session)

        assert result_text is not None, "Agent did not return a final result."

        if expected_substring:
            result_to_check = result_text.lower() if ignore_case else result_text
            substring_to_check = (
                expected_substring.lower() if ignore_case else expected_substring
            )
            assert (
                substring_to_check in result_to_check
            ), f"Assertion failed: Expected '{expected_substring}' not found in agent result: '{result_text}'"

        return result_text


# --- Allure Hook for Step-by-Step Reporting ---


async def record_step(agent: Agent):
    """Hook function that captures and records agent activity at each step."""
    history = agent.state.history
    if not history:
        return

    last_action = history.model_actions()[-1] if history.model_actions() else {}
    action_name = next(iter(last_action)) if last_action else "No action"
    action_params = last_action.get(action_name, {})

    step_title = f"Action: {action_name}"
    if action_params:
        param_str = ", ".join(f"{k}={v}" for k, v in action_params.items())
        step_title += f"({param_str})"

    with allure.step(step_title):
        # Attach Agent Thoughts
        thoughts = history.model_thoughts()
        if thoughts:
            allure.attach(
                str(thoughts[-1]),
                name="Agent Thoughts",
                attachment_type=allure.attachment_type.TEXT,
            )

        # Attach URL
        url = history.urls()[-1] if history.urls() else "N/A"
        allure.attach(
            url,
            name="URL",
            attachment_type=allure.attachment_type.URI_LIST,
        )

        # Attach Step Duration
        last_history_item = history.history[-1] if history.history else None
        if last_history_item and last_history_item.metadata:
            duration = last_history_item.metadata.duration_seconds
            allure.attach(
                f"{duration:.2f}s",
                name="Step Duration",
                attachment_type=allure.attachment_type.TEXT,
            )

        # Attach Screenshot
        if agent.browser_session:
            try:
                screenshot_b64 = await agent.browser_session.take_screenshot()
                if screenshot_b64:
                    screenshot_bytes = base64.b64decode(screenshot_b64)
                    allure.attach(
                        screenshot_bytes,
                        name="Screenshot after Action",
                        attachment_type=allure.attachment_type.PNG,
                    )
            except Exception as e:
                logging.warning(f"Failed to take or attach screenshot: {e}")


# --- Helper Function to Run Agent ---


@allure.step("Running browser agent with task: {task_description}")
async def run_agent_task(
    task_description: str,
    llm: ChatOpenAI,
    browser_session: BrowserSession,
) -> Optional[str]:
    """Initializes and runs the browser agent for a given task using an active browser session."""
    logging.info(f"Running task: {task_description}")

    agent = Agent(
        task=task_description,
        llm=llm,
        browser_session=browser_session,
        name=f"Agent for '{task_description[:50]}...'",
    )

    result = await agent.run(on_step_end=record_step)

    final_text = result.final_result()
    allure.attach(
        final_text,
        name="Agent Final Output",
        attachment_type=allure.attachment_type.TEXT,
    )

    logging.info("Task finished.")
    return final_text
