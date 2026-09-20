"""Starting Chrome for an account, and saying why it did not start.

Shared by main.py and check_selectors.py so both launch the same way and both
explain a failure instead of dumping a traceback. Compatible with Selenium <= 4.9.1.
"""

import logging
import os

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service

import accounts
import log_utils

HEADLESS = os.environ.get("REWARDS_HEADLESS", "").strip().lower() in ("1", "true", "yes")

logger = logging.getLogger(__name__)

# Matched in order against the driver's message, lowercased.
EXPLANATIONS = [
	("chrome instance exited", [
		"Chrome exited during startup, before the driver could connect to it.",
		"Common causes: this profile is open in another Chrome window, a lock left",
		"behind by a browser that was killed, or a profile directory Chrome cannot",
		"write to. Set REWARDS_DRIVER_LOG=chromedriver.log and run again; that",
		"log has Chrome's own reason.",
	]),
	("cannot create default profile directory", [
		"Chrome could not create the profile directory. Check that the current user",
		"can write to it without administrator rights.",
	]),
	("still attached to a running", [
		"This profile is already open in another Chrome window, including one left",
		"over from a previous run or held by a container. Close it and try again.",
	]),
	("only supports chrome version", [
		"chromedriver and Chrome versions do not match. Update chromedriver to your",
		"Chrome version, or remove the old one from PATH / CHROMEDRIVER_PATH.",
	]),
]


def build_options(account: accounts.Account) -> webdriver.ChromeOptions:
	options = webdriver.ChromeOptions()

	options.add_experimental_option("excludeSwitches", ["enable-automation"])
	options.add_experimental_option("useAutomationExtension", False)
	options.add_argument("--disable-blink-features=AutomationControlled")
	options.add_argument(f"--user-data-dir={account.user_data_dir}")
	options.add_argument(f"--profile-directory={account.profile_name}")

	# Spoof User Agent to trick MS Rewards into treating Chromium like Edge
	options.add_argument(
		"--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
		"Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0"
	)

	# Explicitly guide Selenium 4.9.1 to look for the Termux system Chromium
	options.binary_location = "/data/data/com.termux/files/usr/bin/chromium"

	# Termux environment requires headless configurations to function properly
	if HEADLESS or True:  # Overriding to True ensures it handles standard Termux CLI environments
		options.add_argument("--headless=new")
		options.add_argument("--window-size=1920,1080")
		options.add_argument("--no-sandbox")             # Mandatory for Termux
		options.add_argument("--disable-dev-shm-usage")  # Mandatory for Termux
		options.add_argument("--disable-gpu")            # Added for headless stability

	return options


def build_service() -> Service:
	driver_log = os.environ.get("REWARDS_DRIVER_LOG")
	
	# Termux provides its own chromedriver package when installing chromium. 
	# We pass this explicitly to bypass Selenium 4.9's automatic locator mechanics.
	chromedriver_path = (
		os.environ.get("CHROMEDRIVER_PATH") or 
		os.environ.get("MSEDGEDRIVER_PATH") or 
		"/data/data/com.termux/files/usr/bin/chromedriver"
	)

	return Service(
		executable_path=chromedriver_path,
		service_args=["--verbose"] if driver_log else None,
		log_output=driver_log or None,
	)


def explain(exc: Exception) -> list[str]:
	message = str(exc).lower()

	# Since Selenium 4.9.1 handles generic driver errors globally through WebDriverException,
	# we verify missing file logs inside the text trace.
	if "chromedriver" in message or "executable need to be in path" in message:
		return [
			"Selenium could not find chromedriver or Chromium on this machine.",
			"Make sure you ran 'pkg install chromium' inside your Termux terminal.",
		]

	for needle, lines in EXPLANATIONS:
		if needle in message:
			return lines

	return ["The driver's message is below; it did not match a known cause."]


def start_driver(account: accounts.Account):
	"""A Chrome driver for the account, or None after logging why it failed."""
	try:
		# Correct implementation signature for Selenium 4.9.1
		return webdriver.Chrome(options=build_options(account), service=build_service())
	except WebDriverException as exc:
		logger.error("[FAIL] %s: could not start Chrome with this profile.", account.name)
		logger.error("       profile directory: %s", account.user_data_dir)

		for line in explain(exc):
			logger.error("       %s", line)

		logger.error("       driver said: %s", log_utils.exception_summary(exc))

		return None
		
