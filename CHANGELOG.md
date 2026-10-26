# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added - Championship Capabilities (Nov 2026)

These features were added for the Dubai Create AI Agents Championship (Best Business AI Agent category).

#### Real Calendar Booking Integration

- **Calendar provider abstraction** (`calendar.py`): Pluggable calendar backend with support for:
  - **Google Calendar**: Service account or OAuth token authentication
  - **Cal.com**: API key authentication with event type configuration
  - **Mock provider**: In-memory calendar for tests and demos without credentials
- **Automatic provider selection**: Environment-based configuration with graceful fallback to mock mode
- **Calendar sync on booking**: When calendar credentials are configured, `book_appointment` creates real calendar events
- **Updated appointment status**: Appointments are marked "confirmed" when calendar booking succeeds
- **System prompt adaptation**: Agent messaging adjusts based on calendar availability

New environment variables:
- `CALENDAR_PROVIDER`: Force "mock" mode or auto-detect from credentials
- `GOOGLE_CALENDAR_ID`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_CALENDAR_ACCESS_TOKEN`
- `CALCOM_API_KEY`, `CALCOM_EVENT_TYPE_ID`, `CALCOM_API_URL`

#### Urgent Call Escalation

- **New `escalate_urgent` tool**: Flags emergencies for immediate staff attention
- **Urgency levels**: `emergency` (life-threatening), `urgent` (same-day), `high_priority` (callback needed)
- **Staff alerts**: Sends immediate SMS/email notification with structured payload
- **Escalation persistence**: Stored in SQLite for audit trail
- **Emergency number guidance**: Response includes local emergency numbers from config
- **Urgency detection helper**: `detect_urgency()` function identifies emergency keywords
- **Updated system prompt**: Agent instructed to escalate emergencies before directing to 911/999

New notification function: `send_escalation_alert()` in `notify.py`

#### UAE/Dubai Demo Configuration

- **Dubai profile** (`profiles/dubai.yaml`): Pre-configured for Middle East demonstrations
  - Timezone: `Asia/Dubai` (GST, UTC+4)
  - Currency: AED with appropriate pricing
  - Emergency numbers: 999 (Police), 998 (Ambulance), 997 (Fire), 901 (DHA)
  - Friday hours: Afternoon only (14:00-21:00) for prayer time
  - Weekend: Saturday-Sunday open, Friday afternoon
- **Profile loading**: `CLINIC_PROFILE=dubai` or `load_config(profile="dubai")`
- **Emergency number validation**: Relaxed to allow regional numbers while requiring international defaults

New environment variable: `CLINIC_PROFILE`

#### Documentation

- **PRIVACY_NO_PHI.md**: Data handling documentation covering:
  - What is/isn't stored (no PHI, no audio, no transcripts)
  - Third-party data flows (Deepgram, OpenAI, Cartesia, Twilio, etc.)
  - Notification content modes
  - Regional considerations (UAE PDPL, US HIPAA)
  - Production deployment recommendations

#### Database Schema Updates

- `appointments` table: Added `calendar_event_id`, `calendar_provider` columns
- New `escalations` table: Tracks urgent flags with caller details and urgency level

#### Test Coverage

- `test_calendar.py`: Mock provider, availability checks, event creation/cancellation
- `test_escalation.py`: Urgency detection, escalation tool, notification formatting
- `test_profiles.py`: Dubai profile loading, emergency numbers, prompt variations

### Changed

- **`book_appointment` tool description**: Updated to reflect calendar integration capability
- **System prompt**: Now includes escalation instructions and calendar-aware messaging
- **Call summary**: Includes escalation count and details
- **Notification formatting**: Shows confirmed vs pending appointments, escalation alerts

### Technical Notes

- Calendar operations are async; sync happens after tool dispatch
- Escalation callbacks are non-blocking; notification failures don't affect call flow
- Profile loading precedence: explicit path > CLINIC_CONFIG_PATH > profile arg > CLINIC_PROFILE env > default
- All existing tests remain passing with the new features

---

## [0.1.0] - 2026-10-26

### Initial Release

- Pipecat 1.14 voice pipeline with Deepgram STT, OpenAI GPT-4o-mini, Cartesia TTS
- Five tools: `get_hours`, `list_services`, `book_appointment`, `take_message`, `end_call`
- SQLite persistence with consent checks and slot collision protection
- SmallWebRTC browser demo, optional Daily rooms, Twilio phone integration
- Post-call notifications via Twilio SMS and Resend/SMTP email
- 90 passing tests covering tools, config, notifications, and server endpoints
- Next.js marketing site (separate from voice agent)
