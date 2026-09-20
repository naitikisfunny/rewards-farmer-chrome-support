"""Starting Chrome for an account, and saying why it did not start.

Shared by main.py and check_selectors.py so both launch the same way and both
explain a failure instead of dumping a traceback. Compatible with Selenium <= 4.9.1.
"""

import logging
import os
import shutil

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
		"write to. Run 'pkill -f chromium' and try again.",
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
	("session not created", [
		"The session failed to open. This often happens if an old Edge data file",
		"is corrupting Chrome, or a lock file is active. Try wiping your data-dir.",
	]),
]


def build_options(account: accounts.Account) -> webdriver.ChromeOptions:
	options = webdriver.ChromeOptions()

	options.add_experimental_option("excludeSwitches", ["enable-automation"])
	options.add_experimental_option("useAutomationExtension", False)
	options.add_argument("--disable-blink-features=AutomationControlled")
	
	# --- FIXING PROFILE CORRUPTION ---
	# We redirect Chrome to use its own isolated chrome-specific profiles directory
	# instead of reading the broken/pre-existing Edge profile configuration.
	base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	chrome_data_dir = os.path.join(base_dir, "chrome-data-dir", account.name)
	
	# Clear out any leftover lock files dynamically on initialization
	lock_file = os.path.join(chrome_data_dir, "SingletonLock")
	if os.path.islink(lock_file) or os.path.exists(lock_file):
		try:
			os.unlink(lock_file)
		except Exception:
			pass

	options.add_argument(f"--user-data-dir={chrome_data_dir}")
	options.add_argument("--profile-directory=Default")

	# Spoof User Agent to trick MS Rewards into treating Chromium like Edge
	options.add_argument(
		"--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
		"Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0"
	)

	# In Selenium 4.9.1, binary location defaults inside Termux bin path
	options.binary_location = "/data/data/com.termux/files/usr/bin/chromium"

	# Headless parameters optimized for stable low-memory loops
	options.add_argument("--headless=new")
	options.add_argument("--window-size=1920,1080")
	options.add_argument("--no-sandbox")             
	options.add_argument("--disable-dev-shm-usage")  
	options.add_argument("--disable-gpu")            
	options.add_argument("--remote-debugging-port=9222")
	options.add_argument("--disable-extensions")

	return options


def build_service() -> Service:
	# Rely directly on Termux system pathing to avoid custom binary mismatched states
	chromedriver_path = "/data/data/com.termux/files/usr/bin/chromedriver"
	return Service(executable_path=chromedriver_path)


def explain(exc: Exception) -> list[str]:
	message = str(exc).lower()
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
		return webdriver.Chrome(options=build_options(account), service=build_service())
	except WebDriverException as exc:
		logger.error("[FAIL] %s: could not start Chrome with this profile.", account.name)
		for line in explain(exc):
			logger.error("       %s", line)
		logger.error("       driver said: %s", log_utils.exception_summary(exc))
		return None
		
