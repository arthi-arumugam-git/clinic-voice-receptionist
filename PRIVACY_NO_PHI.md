# Privacy and Data Handling

**This document describes what data is stored, retained, and transmitted by this AI voice receptionist demo. It is not a substitute for legal advice, a BAA, or a compliance assessment.**

## What is NOT stored

This application **does not**:

- Record or store audio from calls
- Store raw voice transcripts or conversation logs
- Request or store insurance IDs, payment details, or clinical information
- Request detailed medical history or symptoms
- Store Protected Health Information (PHI) as defined by HIPAA

The receptionist's prompt explicitly prohibits collecting symptoms, medical history, and clinical details. It is instructed to redirect such requests to clinic staff.

## What IS stored locally

The SQLite database (`data/clinic.sqlite3`) stores only:

| Data | Purpose | Example |
|------|---------|---------|
| Call metadata | Session tracking | Call ID, start/end time, status |
| Patient name | Appointment identification | "Jane Smith" |
| Phone number | Callback contact | "+14155550100" |
| Service ID | Requested service type | "dental_exam" |
| Appointment date/time | Scheduling | "2027-01-15T10:00:00" |
| Administrative notes | Brief context | "Prefers morning appointments" |
| Message text | Staff messages | "Please call about billing question" |
| Escalation details | Urgent alerts | Phone, brief reason, urgency level |

## Data flow to third parties

| Service | Data sent | Purpose |
|---------|-----------|---------|
| Deepgram | Audio stream | Speech-to-text transcription |
| OpenAI | Text conversation | Language model processing |
| Cartesia/ElevenLabs | Text responses | Text-to-speech synthesis |
| Twilio (if configured) | Audio, SMS content | Phone transport, notifications |
| Google Calendar (if configured) | Appointment details | Calendar booking |
| Cal.com (if configured) | Appointment details | Calendar booking |
| Resend/SMTP (if configured) | Summary text | Email notifications |

Each provider has their own data retention and privacy policies. Review their terms before use with real caller data.

## Notification content

Staff notifications (SMS/email) can operate in two modes:

1. **Default (NOTIFY_INCLUDE_DETAILS=false):**
   - Call reference ID
   - Call status
   - Count of appointments/messages
   - No personal details transmitted

2. **Details mode (NOTIFY_INCLUDE_DETAILS=true):**
   - Includes names, phone numbers, appointment times
   - Only use in appropriate demo environments

## Data retention

This demo does **not** implement:

- Automatic data deletion or retention limits
- Data encryption at rest
- Access controls or audit logging
- GDPR deletion requests
- HIPAA-compliant retention policies

The operator is responsible for:
- Securing the SQLite database file
- Implementing appropriate retention policies
- Deleting data when no longer needed
- Restricting access to authorized staff

## Regional considerations

### UAE/Dubai (PDPL, DHA)

The Dubai profile (`profiles/dubai.yaml`) provides UAE-appropriate settings but does not implement UAE Personal Data Protection Law (PDPL) compliance. Operators deploying in the UAE should:

- Review DHA (Dubai Health Authority) telehealth guidelines
- Ensure appropriate data residency
- Obtain necessary licenses and approvals

### US (HIPAA)

This demo is **not HIPAA-compliant**. It does not:

- Execute Business Associate Agreements (BAAs)
- Implement required administrative safeguards
- Provide required technical safeguards
- Support required physical safeguards

Do not use with real patient data without a complete compliance assessment and appropriate vendor agreements.

## Recommendations for production use

1. **Use fictional data** for all demonstrations
2. **Review provider policies** for each integrated service
3. **Implement encryption** at rest and in transit
4. **Add access controls** before any staff use
5. **Consult legal counsel** before patient deployment
6. **Execute BAAs** with all providers handling PHI
7. **Implement audit logging** for compliance
8. **Set retention policies** and automate deletion

## Contact

For questions about this demo's data handling, contact the repository maintainer.

---

*Last updated: November 2026*
*This document describes the demo as provided and does not constitute legal advice.*
