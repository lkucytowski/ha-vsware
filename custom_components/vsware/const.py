DOMAIN = "vsware"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_PARENT_ID = "parent_id"
CONF_LEARNER_ID = "learner_id"
CONF_DISPLAY_NAME = "display_name"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_WEBSITE_URL = "website_url"

DEFAULT_SCAN_INTERVAL = 3600  # seconds

LOGIN_PATH = "/tokenapiV2/login"
LEARNERS_PATH = "/control/household/learners"
SECURITY_ROLES_PATH = "/control/securityroles/user/"
ATTENDANCE_PATH = "/control/parental/{learner_id}/attendance/{parent_id}/overview"
BEHAVIOUR_PATH = "/control/behaviour/incident/fetch/ALL/0/current?currentYear=true"
