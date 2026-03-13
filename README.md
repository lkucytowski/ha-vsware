# VSware Home Assistant Integration

A custom [HACS](https://hacs.xyz/) integration for [Home Assistant](https://www.home-assistant.io/) that connects to the [VSware](https://www.vsware.ie/) school management system and exposes student attendance and behaviour data as entities.

## Features

- **Attendance tracking** — total school days, present days, absent days, partial absences, and unexplained absences, each with a full list of dates as attributes
- **Behaviour monitoring** — positive and negative points, progress score, and most recent behaviour entry with full details
- **Multi-student support** — if your account has multiple children, each is configured as a separate integration entry with its own device
- **Automatic discovery** — the integration fetches the student list and academic year ID automatically; no manual ID entry required
- **Token management** — authenticates on first use and re-authenticates transparently on token expiry

## Supported Entities

Each student gets their own HA device with the following sensors:

### Attendance

| Entity | State | Attributes |
|---|---|---|
| Total School Days | Number of school days | — |
| Present Days | Count of days present | `dates` — list of dates |
| Absent Days | Count of days absent | `dates` — list of dates |
| Partially Absent Days | Count of partial absence days | `dates` — list of dates |
| Unexplained Absences | Count of unexplained absences | `dates` — list of dates |

### Behaviour

| Entity | State | Attributes |
|---|---|---|
| Positive Points | Total positive behaviour points | — |
| Negative Points | Total negative behaviour points | — |
| Progress Score | Starting points + total points earned | — |
| Most Recent Points | `Positive` or `Negative` | `points`, `subject`, `comment`, `date`, `raised_by` |

## Requirements

- Home Assistant 2024.1 or newer
- A VSware parent/guardian account with access to the parental portal
- Your school's VSware app URL (e.g. `https://yourschool.app.vsware.ie`)

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** → click the three-dot menu → **Custom repositories**
3. Add this repository URL and select category **Integration**
4. Search for **VSware** and install it
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/vsware` folder into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **VSware**
3. Enter your details:

| Field | Description | Example |
|---|---|---|
| Website URL | Your school's VSware app URL | `https://yourschool.app.vsware.ie` |
| Username | Your VSware login username | `jane.doe` |
| Password | Your VSware login password | |
| Scan interval | How often to refresh data (seconds) | `3600` |

4. After successful login, select the student you want to monitor from the dropdown
5. The integration will create a device for the selected student with all sensors

> **Note:** The integration derives the API URL automatically from the website URL by removing the `.app` subdomain segment.

## Multiple Students

To monitor more than one student, add the integration multiple times — once per student. Each will appear as a separate device in Home Assistant.

## Data Refresh

By default, data is refreshed every **3600 seconds (1 hour)**. You can change this during setup. The minimum practical interval depends on how frequently VSware updates its data; for attendance, once or twice a day is typically sufficient.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `invalid_auth` error during setup | Wrong username or password |
| `cannot_fetch_user` error | Logged in but API returned unexpected data — check the website URL |
| `no_learners` error | Account has no linked students |
| Sensors show `unavailable` | API unreachable or token refresh failed — check HA logs |

Enable debug logging by adding to `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.vsware: debug
```

## Privacy

Your credentials are stored in the Home Assistant config entry (encrypted at rest by HA). They are only used to authenticate with the VSware API and are never sent anywhere else.

## License

MIT
