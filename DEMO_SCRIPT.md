# A 60-second clinic receptionist demo

**Before the demo:** configure `.env`, run `python bot.py`, and open `http://localhost:7860/client/`. Use headphones. Choose a future Monday at 10 a.m. in the configured `America/New_York` timezone and an unused local slot. Have `clinic_config.yaml` and a terminal ready. All names and phone numbers below are fictional. Optional staff notifications can be enabled; the local database works without them.

| Time | Say / do | What it demonstrates |
| --- | --- | --- |
| 0–6s | Presenter: “When your team is with a patient, this AI receptionist can answer the next call.” Connect in the browser UI. | Browser voice demo, no phone setup required |
| 6–14s | Bot introduces itself as the clinic’s AI receptionist. Caller: “What time do you close on Friday?” | Honest AI disclosure; configured hours (4 p.m.) |
| 14–22s | Caller: “What does a dental exam cost?” | Configured service price ($95); no invented coverage promise |
| 22–38s | Caller: “I’d like to request a dental exam on [full future Monday date] at ten a.m. I’m Alex Demo. My callback number is 202-555-0148.” Respond if it asks to clarify. | Function calling; a future date in clinic hours |
| 38–47s | Let the bot read the details back. Caller: “Yes, please save that request.” | Consent before storage; SQLite appointment request pending staff confirmation |
| 47–53s | Caller: “That’s all, goodbye.” Let the goodbye finish. | Graceful end-call and optional post-call staff notification |
| 53–60s | Presenter runs the export command below: “Your team receives the request and confirms the appointment. Start with a 14-day free pilot; setup takes one week.” | Reviewable saved outcome and clear staff handoff |

```bash
python scripts/export_csv.py --output exports/appointments.csv
```

Rehearse once: network latency and speaking pace can make a live call longer than sixty seconds. Keep the hours and price questions short if needed. If you repeat the demo, choose another unoccupied future slot; the local store correctly prevents overlapping requests.

**Optional follow-up demonstrations:** “Please take a message asking the office to call me about parking,” then confirm the read-back. For a separate safety check, say “This is an emergency.” The expected response is an immediate direction to local emergency services, never medical advice or a claim that help has been dispatched. This is a scripted evaluation with fictional data, not an emergency service.

**If credentials or microphone access are unavailable:** show the landing page’s clearly labeled simulated conversation preview and the offline tests (`python -m pytest -q`). State that the preview is simulated and that a live provider call has not been demonstrated.
