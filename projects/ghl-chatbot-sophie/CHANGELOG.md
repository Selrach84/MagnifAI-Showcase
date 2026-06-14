# Sophie — Changelog & Script Reference

## v2.1 — Initial production build

**Model:** OpenAI GPT 4.1 via GHL Conversation AI

### Capabilities
- Lead qualification via income/equity gates
- Sequential 4-question info collection (name, email, mobile, timezone)
- GHL calendar slot display (up to 6 slots)
- Booking confirmation with summary
- Nurture flow for non-qualified leads
- Contact creation in GHL CRM on booking

### v2.1 → v2.2 Changes
- Replaced bundled questions with sequential single-question flow
- Timezone auto-inference from city (removed numbered menu)
- Added summary confirmation step before booking
- Enhanced post-booking message with spam folder heads-up
- GHL contact field updates on confirmation
- Appointment Booking trigger on confirmation

### Testing
- Stress test: 12/12 messages passed
- Backend verification: All fields captured correctly
- Booking audit: Calendar integration verified
