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
		"behind by a browser that was killed.",
	]),
	("cannot create default profile directory", [
		"Chrome could not create the profile directory. Check file permissions.",
	]),
	("still attached to a running", [
		"This profile is already open in another Chrome window.",
	]),
	("session not created", [
		"The session failed to open. Wiping the isolated chrome directory will fix it.",
	]),
]


def build_options(account: accounts.Account) -> webdriver.ChromeOptions:
	options = webdriver.ChromeOptions()

	options.add_argument("--disable-blink-features=AutomationControlled")
	
	# Isolated profile initialization directory setup
	base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	chrome_data_dir = os.path.join(base_dir, "chrome-data-dir", account.name)
	
	# Instantly drop stale filesystem lock hooks
	for lock_name in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
		lock_file = os.path.join(chrome_data_dir, lock_name)
		if os.path.islink(lock_file) or os.path.exists(lock_file):
			try:
				os.unlink(lock_file)
			except Exception:
				pass

	options.add_argument(f"--user-data-dir={chrome_data_dir}")

	# Spoof User Agent to trick MS Rewards into treating Chromium like Edge
	options.add_argument(
		"--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
		"Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0"
	)

	# Direct pathing constraints for Termux packages
	options.binary_location = "/data/data/com.termux/files/usr/bin/chromium"

	# Headless parameters optimized for standard Android execution loops
	options.add_argument("--headless")  # Force classic headless method for legacy driver support
	options.add_argument("--window-size=1920,1080")
	options.add_argument("--no-sandbox")             
	options.add_argument("--disable-dev-shm-usage")  
	options.add_argument("--disable-gpu")            
	options.add_argument("--remote-debugging-port=9222")
	options.add_argument("--disable-extensions")
	
	# CRITICAL FOR HEADLESS CRASH FIXES IN TERMUX:
	options.add_argument("--disable-setuid-sandbox")
	options.add_argument("--disable-dev-tools")

	return options


def build_service() -> Service:
	chromedriver_path = "/data/data/com.termux/files/usr/bin/chromedriver"
	return Service(executable_path=chromedriver_path)


def explain(exc: Exception) -> list[str]:
	message = str(exc).lower()
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
		
