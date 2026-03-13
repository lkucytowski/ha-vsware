from urllib.parse import urlparse, urlunparse

DOMAIN = "vsware"


def derive_api_base_url(website_url: str) -> str:
    """Derive the API base URL from the website URL by removing the 'app' subdomain segment."""
    parsed = urlparse(website_url.rstrip("/"))
    api_netloc = parsed.netloc.replace(".app.", ".")
    return urlunparse(parsed._replace(netloc=api_netloc))

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_ACADEMIC_YEAR_ID = "academic_year_id"
CONF_LEARNER_ID = "learner_id"
CONF_DISPLAY_NAME = "display_name"
CONF_PREFERRED_NAME = "preferred_name"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_WEBSITE_URL = "website_url"

DEFAULT_SCAN_INTERVAL = 60  # minutes
MIN_SCAN_INTERVAL = 60  # minutes

LOGIN_PATH = "/tokenapiV2/login"
LEARNERS_PATH = "/control/household/learners"
SECURITY_ROLES_PATH = "/control/securityroles/user"
ATTENDANCE_PATH = "/control/parental/{learner_id}/attendance/{academic_year_id}/overview"
BEHAVIOUR_PATH = "/control/behaviour/incident/fetch/ALL/0/current?currentYear=true"
