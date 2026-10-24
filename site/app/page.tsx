import { CallPreview } from "./call-preview";

const configuredEmail = process.env.NEXT_PUBLIC_CONTACT_EMAIL?.trim();
const contactEmail = configuredEmail && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(configuredEmail)
  ? configuredEmail
  : "hello@example.com";
const demoContact = contactEmail === "hello@example.com";
const contactHref = `mailto:${contactEmail}?subject=${encodeURIComponent("Clinic Voice: 14-day pilot")}&body=${encodeURIComponent("Hi Arthi,\n\nI’m interested in a Clinic Voice pilot.\n\nClinic name:\nClinic website:\nBest time to connect:\n\nThanks!")}`;

const faqs = [
  {
    question: "Will this replace my front desk team?",
    answer: "It gives your team backup. The receptionist can answer routine questions and capture appointment requests when staff are helping patients, on another call, or away. Your team stays in control of confirmations and follow-ups.",
  },
  {
    question: "Can it book into our practice management system?",
    answer: "This demo captures appointment requests for staff confirmation and exports them to a spreadsheet. Direct calendar or practice management integration is a separate setup discussion. The assistant never promises an unverified appointment slot.",
  },
  {
    question: "What happens with medical questions or emergencies?",
    answer: "The assistant does not diagnose, recommend treatment, or give medical advice. It directs emergencies to local emergency services: 911 in the US, 000 in Australia, or 999 in the UK. Non-urgent clinical questions become a message for your team.",
  },
  {
    question: "How does the 14-day free pilot work?",
    answer: "We start with your clinic details and agree on a limited pilot scope. Try the experience for 14 days before deciding on the ongoing service. The proposed paid service is a $1,500 setup completed in one week, then $400 per month. Usage and integration needs are agreed before activation.",
  },
  {
    question: "Is the demo HIPAA compliant?",
    answer: "This repository is a demonstration, not a HIPAA-compliant product out of the box. Use synthetic patient data for testing. Before handling real patient information, your clinic needs appropriate vendor agreements, security controls, access policies, and a compliance review.",
  },
  {
    question: "Can we keep our existing phone number?",
    answer: "A phone setup can use call forwarding to a connected number, depending on your phone provider. We confirm routing, business hours, and a fallback plan with you during setup. You can also try the browser demo before connecting a phone line.",
  },
];

function Brand({ footer = false }: { footer?: boolean }) {
  return (
    <a href="#" className={`brand${footer ? " footer-brand" : ""}`} aria-label="Clinic Voice home">
      <span className="brand-mark" aria-hidden="true"><span /><span /><span /></span>
      <span>clinic voice<span className="brand-period">.</span></span>
    </a>
  );
}

function Arrow() {
  return <span className="arrow" aria-hidden="true">↗</span>;
}

export default function Home() {
  return (
    <>
      <a className="skip-link" href="#main-content">Skip to content</a>
      <header className="site-header">
        <div className="container header-inner">
          <Brand />
          <nav aria-label="Main navigation">
            <a href="#how-it-works">How it works</a>
            <a href="#features">Features</a>
            <a href="#pricing">Pricing</a>
          </nav>
          <a className="button button-small" href={contactHref}>Start your free pilot <Arrow /></a>
        </div>
      </header>

      <main id="main-content">
        <section className="hero container">
          <div className="hero-copy">
            <p className="eyebrow">AI receptionist for clinics</p>
            <h1>Never miss<br />a patient’s <em>call.</em></h1>
            <p className="hero-description">A warm welcome, answers, and appointment requests. Even when your team is busy or your clinic is closed.</p>
            <div className="hero-actions">
              <a className="button" href={contactHref}>Start your free pilot <Arrow /></a>
              <a className="text-link" href="#sample-call">Explore a sample call <span aria-hidden="true">↘</span></a>
            </div>
            <div className="pilot-note"><span className="note-line" />14 days to see the difference.</div>
          </div>
          <CallPreview />
        </section>

        <div className="intro-strip">
          <div className="container intro-strip-inner">
            <p>Built for the people<br /><strong>who care for people.</strong></p>
            <div className="clinic-types" aria-label="Designed for these clinics">
              <span>Dental practices</span><span>Medical clinics</span><span>Independent practitioners</span>
            </div>
          </div>
        </div>

        <section className="section container problem-section" aria-labelledby="problem-title">
          <div className="problem-copy">
            <h2 id="problem-title">You can’t be in<br />two conversations<br /><em>at once.</em></h2>
            <p>A patient at the desk deserves your attention. So does the person calling. Give both a good first impression.</p>
            <a className="text-link" href="#how-it-works">Meet your extra pair of hands <span aria-hidden="true">↓</span></a>
          </div>
          <div className="problem-list">
            <article><span className="situation-symbol" aria-hidden="true">↗</span><div><h3>The call during a busy morning</h3><p>New patient inquiries shouldn’t have to compete with check-ins, paperwork, and the waiting room.</p></div></article>
            <article><span className="situation-symbol" aria-hidden="true">◷</span><div><h3>The call after you’ve closed</h3><p>Patients call when life gives them a moment. Capture their request before they try another clinic.</p></div></article>
            <article><span className="situation-symbol" aria-hidden="true">↻</span><div><h3>The voicemail nobody gets to</h3><p>A missed call can mean a missed appointment. Turn a callback queue into clear, useful follow-ups.</p></div></article>
          </div>
        </section>

        <section className="how-section section" id="how-it-works" aria-labelledby="how-title">
          <div className="container">
            <div className="section-heading centered-heading"><h2 id="how-title">Your clinic. Your voice.<br /><em>A little more available.</em></h2><p>From first hello to the next step, every call follows your clinic’s instructions.</p></div>
            <ol className="process-grid">
              <li><div className="process-visual visual-greeting"><span className="greeting-line">Hello, you’ve reached</span><span className="greeting-clinic">your clinic.</span><div className="small-wave" aria-hidden="true">{[10, 18, 26, 15, 34, 23, 16, 29, 19, 10].map((h, i) => <span key={i} style={{ height: h }} />)}</div></div><div className="process-title"><span>01</span><h3>A friendly first hello</h3></div><p>Calls reach an AI receptionist that introduces itself and welcomes the caller in your clinic’s name.</p></li>
              <li><div className="process-visual visual-requests"><span>“Are you open on Saturday?”</span><span>“I’d like to book a cleaning.”</span><span>“Could you take a message?”</span></div><div className="process-title"><span>02</span><h3>The right next step</h3></div><p>It answers from your clinic details, captures appointment requests, or takes a message for your team.</p></li>
              <li><div className="process-visual visual-summary"><div className="summary-paper"><span className="summary-heading">Your next follow-up</span><strong>New appointment request</strong><span>Preferred time captured</span><span className="summary-status">Ready for staff confirmation <span aria-hidden="true">✓</span></span></div></div><div className="process-title"><span>03</span><h3>Your team takes it from here</h3></div><p>A concise call summary helps staff follow up. Choose email or SMS notifications for your workflow.</p></li>
            </ol>
          </div>
        </section>

        <section className="section container features-section" id="features" aria-labelledby="features-title">
          <div className="section-heading"><p className="eyebrow">Thoughtful by design</p><h2 id="features-title">The everyday details.<br /><em>Already taken care of.</em></h2></div>
          <div className="feature-layout">
            <article className="feature-spotlight">
              <div className="availability-art" aria-hidden="true"><span className="clock-face"><span className="clock-hand hour-hand" /><span className="clock-hand minute-hand" /></span><span className="availability-caption">A welcome after hours, too.</span></div>
              <h3>Your clinic doesn’t have to be open<br />to make a good first impression.</h3>
              <p>Give callers a helpful next step outside business hours, during lunch breaks, and when the front desk needs a moment.</p>
            </article>
            <div className="feature-details">
              <article><span className="feature-number">01</span><div><h3>Answers that sound like your clinic</h3><p>Hours, location, services, prices, and insurance details come from your own clinic information.</p></div></article>
              <article><span className="feature-number">02</span><div><h3>Appointment requests, organized</h3><p>Capture contact details and preferred times. Your team confirms availability before anything is promised.</p></div></article>
              <article><span className="feature-number">03</span><div><h3>Follow-ups without the detective work</h3><p>Save messages and get a call summary through your configured email or SMS channel.</p></div></article>
              <article><span className="feature-number">04</span><div><h3>A clear boundary around clinical care</h3><p>No diagnoses or medical advice. Clinical questions go to your team; emergencies go to local emergency services.</p></div></article>
            </div>
          </div>
        </section>

        <section className="section pricing-section" id="pricing" aria-labelledby="pricing-title">
          <div className="container pricing-layout">
            <div className="pricing-copy"><p className="eyebrow">A simple place to start</p><h2 id="pricing-title">More calls answered.<br /><em>Less on your plate.</em></h2><p>Try it with your clinic’s details. See how it fits your front desk before choosing the ongoing service.</p><div className="pilot-stamp"><strong>14</strong><span>day<br />free pilot</span></div></div>
            <div className="price-card">
              <div className="price-card-top"><span>YOUR EXTRA FRONT DESK</span><span className="price-tag">One clinic</span></div>
              <div className="monthly-price"><span className="currency">$</span><strong>400</strong><span>/ month</span></div>
              <p className="setup-price">$1,500 one-time setup <span>·</span> Ready in 1 week</p>
              <div className="price-divider" />
              <ul className="price-includes"><li>Configured for your clinic and services</li><li>Call handling and appointment requests</li><li>Messages and after-call summaries</li><li>A guided setup and handover</li></ul>
              <a className="button price-button" href={contactHref}>Start your free pilot <Arrow /></a>
              <p className="price-fine-print">14 days free to try. Usage allowances, provider charges, and any integrations are agreed before activation.</p>
            </div>
          </div>
        </section>

        <section className="section container faq-section" id="faq" aria-labelledby="faq-title">
          <div className="faq-heading"><h2 id="faq-title">Good questions.<br /><em>Clear answers.</em></h2><p>A few things worth knowing before<br className="desktop-break" /> your first hello.</p></div>
          <div className="faq-list">{faqs.map((faq) => <details key={faq.question}><summary>{faq.question}<span aria-hidden="true">+</span></summary><p>{faq.answer}</p></details>)}</div>
        </section>

        <section className="final-cta container" aria-labelledby="cta-title"><span className="cta-mark brand-mark" aria-hidden="true"><span /><span /><span /></span><h2 id="cta-title">A little less ringing.<br /><em>A little more caring.</em></h2><p>Let’s give every caller a warm welcome.</p><a className="button" href={contactHref}>Start your free pilot <Arrow /></a><span className="cta-note">14-day free pilot. Set up around your clinic.</span></section>
      </main>

      <footer className="site-footer container">
        <div className="footer-top"><Brand footer /><p>A warm welcome. Every time.</p><a className="text-link" href="#faq">Questions & answers <Arrow /></a></div>
        <div className="footer-bottom"><span>Built by Arthi Arumugam</span><span>For dental and medical clinics</span><span>AI reception. Human care.</span></div>
        {demoContact && <p className="demo-contact-note">Demo website: contact links use hello@example.com. Set a real contact address before publishing.</p>}
      </footer>
    </>
  );
}
