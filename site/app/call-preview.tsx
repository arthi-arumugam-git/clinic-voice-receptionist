"use client";

import { useState } from "react";

const scenarios = [
  {
    label: "Appointment",
    title: "A new patient. A warm welcome.",
    caller: "Hi! I’d like to book a dental cleaning.",
    assistant:
      "Of course. I can take your preferred time and contact details, and our team will confirm your appointment.",
    outcome: "Appointment request captured",
    detail: "Ready for your team to confirm",
  },
  {
    label: "Clinic hours",
    title: "A quick question, answered.",
    caller: "Are you open on Saturday?",
    assistant:
      "Our sample clinic is closed on Saturday. We’re open Monday through Friday. Would you like me to take an appointment request?",
    outcome: "An answer from your clinic’s details",
    detail: "Hours, services, prices, and insurance",
  },
  {
    label: "A message",
    title: "A message that reaches your team.",
    caller: "Could someone call me about my visit?",
    assistant:
      "Absolutely. May I have your name, callback number, and a brief message for the front desk?",
    outcome: "Callback message captured",
    detail: "A clear follow-up for your front desk",
  },
];

export function CallPreview() {
  const [active, setActive] = useState(0);
  const scenario = scenarios[active];

  return (
    <section className="call-preview" id="sample-call" aria-label="Interactive sample call">
      <div className="preview-header">
        <span className="mini-brand">clinic voice</span>
        <span className="sample-tag">Sample conversation</span>
      </div>
      <div className="voice-portrait" aria-hidden="true">
        <div className="voice-orbit orbit-one" />
        <div className="voice-orbit orbit-two" />
        <div className="voice-orbit orbit-three" />
        <div className="voice-core">
          <div className="waveform">
            {[18, 31, 47, 29, 58, 41, 25, 47, 32, 17, 26].map((height, index) => (
              <span key={index} style={{ height: `${height}px` }} />
            ))}
          </div>
        </div>
      </div>
      <div className="preview-title">{scenario.title}</div>
      <div className="conversation" aria-live="polite" aria-atomic="true">
        <div className="message caller-message">
          <span className="speaker">Caller</span>
          <p>{scenario.caller}</p>
        </div>
        <div className="message assistant-message">
          <span className="speaker">Your AI receptionist</span>
          <p>{scenario.assistant}</p>
        </div>
        <div className="call-outcome">
          <span className="outcome-check" aria-hidden="true">✓</span>
          <div><strong>{scenario.outcome}</strong><span>{scenario.detail}</span></div>
        </div>
      </div>
      <div className="scenario-options" role="group" aria-label="Choose a sample call">
        {scenarios.map((item, index) => (
          <button
            type="button"
            key={item.label}
            aria-pressed={active === index}
            onClick={() => setActive(index)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <p className="simulation-note">Interactive transcript. Simulated call, no microphone or audio.</p>
    </section>
  );
}
