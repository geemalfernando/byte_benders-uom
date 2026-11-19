const fs = require('fs');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun, AlignmentType,
  HeadingLevel, WidthType, ShadingType, BorderStyle, LevelFormat, Footer, Header, PageNumber, ExternalHyperlink } = require('docx');

const FIG = require('path').join(__dirname, '../../') + 'docs/figures/';
const NAVY = '1C5CAB', GREY = '595959', W = 9638; // A4 text width with 2cm margins (DXA)
const r = (t, o = {}) => new TextRun({ text: t, ...o });
const P = (kids, o = {}) => new Paragraph({ spacing: { after: 100, line: 264 }, ...o, children: (typeof kids === 'string') ? [r(kids)] : kids });
const H1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [r(t)] });
const H2 = t => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [r(t)] });
const B = (kids, lvl = 0) => new Paragraph({ numbering: { reference: 'b', level: lvl }, spacing: { after: 50, line: 252 }, children: (typeof kids === 'string') ? [r(kids)] : kids });
const bold = t => r(t, { bold: true });
const src = t => new Paragraph({ spacing: { after: 140 }, children: [r(t, { size: 16, color: GREY, italics: true })] });
const border = { style: BorderStyle.SINGLE, size: 4, color: 'BFBFBF' };
const borders = { top: border, bottom: border, left: border, right: border };
function table(widths, rows, opt = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  return new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: rows.map((row, i) => new TableRow({ tableHeader: i === 0, cantSplit: true, children: row.map((cell, j) => new TableCell({
      borders, width: { size: widths[j], type: WidthType.DXA },
      shading: i === 0 ? { fill: NAVY, type: ShadingType.CLEAR, color: 'auto' } : (opt.zebra && i % 2 === 0 ? { fill: 'F2F6FB', type: ShadingType.CLEAR, color: 'auto' } : undefined),
      margins: { top: 50, bottom: 50, left: 90, right: 90 },
      children: [new Paragraph({ spacing: { after: 0, line: 240 }, children: [r(String(cell), { size: opt.size || 18, bold: i === 0 || (opt.boldFirst && j === 0), color: i === 0 ? 'FFFFFF' : undefined })] })]
    })) }))
  });
}
const gap = () => new Paragraph({ spacing: { after: 60 }, children: [] });
const img = (file, w, h) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new ImageRun({ type: 'png', data: fs.readFileSync(FIG + file), transformation: { width: w, height: h }, altText: { title: file, description: file, name: file } })] });
const caption = t => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 }, children: [r(t, { size: 17, italics: true, color: GREY })] });

const bm = JSON.parse(fs.readFileSync(require('path').join(__dirname, '../../') + 'project/reports/benchmark.json'));
const pc = x => x === null ? 'n/a' : (100 * x).toFixed(1) + '%';
const D = bm.datasets, rob = bm.robustness;

const body = [
  // ---------- cover block ----------
  new Paragraph({ spacing: { after: 40 }, children: [r('INNODATA AI CATALYST 2026  ·  UNIVERSITY TRACK  ·  PROJECT PROPOSAL', { size: 18, color: GREY, bold: true })] }),
  new Paragraph({ spacing: { after: 40 }, children: [r('Rakshaka AI', { size: 52, bold: true, color: NAVY })] }),
  new Paragraph({ spacing: { after: 160 }, children: [r('A multi-agent second opinion on scam messages, in Sinhala, Tamil and English', { size: 26, color: '333333' })] }),
  table([2400, 7238], [
    ['Item', 'Details'],
    ['Team', 'Byte Benders, University of Moratuwa (BSc (Hons) in Information Technology)'],
    ['Members', 'Geemal Fernando (team leader) · Thisuka Mahiru · Chanith Wijekoon · Pamindu Piumaka'],
    ['Registration ref.', 'AIC26-DADFC32AB79D (University Track)'],
    ['Domain', 'Cybersecurity: consumer fraud and social-engineering defence'],
    ['Repository', 'https://github.com/geemalfernando/byte_benders-uom'],
    ['Status (19 Nov 2026)', 'Working multi-agent pipeline, single-agent baseline and benchmark harness in the repository; Phase 1 MVP due 29 Nov'],
  ], { boldFirst: true, size: 18 }),
  gap(),
  H2('Summary'),
  P([r('Scam SMS and WhatsApp messages are one of the cheapest, most scalable attacks on ordinary people. They arrive in the user\'s own language, look official, and push for action within minutes. Rakshaka AI lets anyone forward a suspicious message and get a verdict (SCAM, UNCERTAIN or LIKELY SAFE), the reason, and one clear next step in their language. '),
    r('It is built as a team of nine agents', { bold: true }),
    r(': privacy intake, language, content, social-engineering tactics, link and sender intelligence, campaign memory, a drift sentinel, an arbiter that resolves conflicts, and an explainer whose every reply is validated. Unsure messages go to a human reviewer, and their labels feed safe retraining. On our current test sets the multi-agent system catches more scams than a single agent with the same data and model. On new scam tactics it catches 95.5% against 87.1%, and on link-based impersonation 78.1% against 12.5%, with no false alarms on any set. It is slower (about 9–14 ms against 2 ms per message), and we state where it is worse.')]),

  // ---------- 1 problem ----------
  H1('1. The problem and its context'),
  P([bold('What happens. '), r('A pensioner receives "SLKPOST: customs fee unpaid, pay Rs 92 at slpost-lk.top within 24 hours". The link opens a copy of a payment page; the card details entered there are used within the hour. The same campaign appears in four wordings and two sender names in three days, in Sinhala, English and code-mixed Singlish. A retired judge in Sri Lanka lost about Rs 400,000 after a fake postal SMS asked for a parcel fee of under Rs 100.')]),
  P([bold('Who is affected. '), r('Everyone with a phone, but the harm concentrates on people least able to check: older adults, welfare recipients and first-time digital-banking users. Sri Lanka has 2.74 million people aged 65+, 727,092 government pensioners, 1.25 million Aswesuma welfare beneficiaries and 30.3 million mobile connections, and 80.3% of people live in rural areas. The Central Bank Governor names rural, low-income, senior and young people as the most vulnerable. Globally the pattern is the same: in the United States, people aged 60 and over reported about USD 7.7 billion of the USD 20.9 billion lost to internet crime in 2025.')]),
  P([bold('Why it remains unsolved. '), r('Defences sit either weeks before the message (awareness campaigns) or after the loss (reporting, blocking known links). Nothing helps at the moment the message arrives. Our research on the current options found these gaps:')]),
  B([bold('No local-language checker. '), r('No content checker we could find supports Sinhala or Tamil. Global tools (Google Messages scam detection, WhatsApp scam alerts) are not offered in Sri Lanka or do not cover these languages. Singapore\'s ScamShield shows that forward-to-check works nationally, but it replies only in English.')]),
  B([bold('Tactics change faster than warnings. '), r('Official 2026 warnings describe a new lure almost every month: a fake bank alert (Jan), a fake post office (Mar), fake digital-ID registration (Apr), a fake GovPay traffic fine (May), a fake ID-office notice (Jun) and a fake welfare official (Jul).')]),
  B([bold('One signal is not enough. '), r('Wording, link, sender and tactic each catch a different part of the problem. A model of the wording alone does not know that "b0c-secure.com" is not the Bank of Ceylon. A link checker does not see that a message asks for an OTP.')]),
  P([bold('Why now. '), r('Fast-payment transfers in Sri Lanka grew 27.7% year on year (Q1 2026). A new digital ID is rolling out and is already used as a lure. The Personal Data Protection Act\'s main obligations start on 1 January 2027, which favours designs that keep personal data out of analysis. Sri Lanka CERT received more than 12,650 cyber complaints in 2025 and over 360 online financial-fraud incidents in a single month (June 2026).')]),
  src('Sources: Daily Mirror (24 Nov 2025); Census 2024 (DCS); Dept. of Pensions (Feb 2025); Ada Derana (3 Jun, 11 Sep 2026); DataReportal Digital 2026; CBSL Governor "Be Scam Proof" (2 Jun 2026); Sunday Times (1 Jan 2026); CBSL Payments Bulletin Q1 2026; SLCERT, Sri Lanka Post, DRP, Police, WBB warnings via Newswire/Newsfirst (Jan–Jul 2026); scamshield.org.sg; AARP / FBI IC3 2025.'),

  // ---------- 2 research ----------
  H1('2. Research findings and global impact'),
  table([3000, 6638], [
    ['Finding', 'Evidence'],
    ['Scale', 'GASA and Feedzai estimate USD 442 billion lost to scams in the 12 months before their 2025 survey of 46,000 adults in 42 markets; 57% of adults experienced a scam and 23% lost money.'],
    ['Speed', 'In the same survey, 64% of scams were over within a day of first contact, so help has to come at the moment of contact, not after.'],
    ['Growth and organisation', 'UNODC estimates scam losses of USD 88.3–114.1 billion in East and Southeast Asia, Australia and New Zealand in 2025, at least three times the 2023 estimate, driven by industrial-scale scam compounds.'],
    ['Record reported losses', 'The FBI IC3 logged 1,008,597 complaints and USD 20.9 billion in losses in 2025, up 26%. It recorded AI-related complaints for the first time (22,364, USD 893 million).'],
    ['Who loses most', 'In IC3 data, older adults lose the most. In Sri Lanka, SLCERT and the CBSL name the elderly, rural and first-time internet users.'],
    ['Local signal', 'SLCERT: 12,650+ complaints in 2025. Police receive online financial-fraud complaints daily, mainly via Telegram and WhatsApp. Rural computer literacy is 34.5%, and 14.9% in the estate sector.'],
  ], { boldFirst: true, zebra: true }),
  P([bold('Dimensions of impact. '), r('Economic: direct losses, plus bank dispute handling and helpline load. Social: loss of trust in digital payments just as governments push them. Humanitarian: UNODC links scam compounds to trafficking for forced criminality, with people from at least 80 countries found inside them. Every message that is not acted on reduces the return on that model. The language gap is global too: the same design applies to any market where scams arrive in languages that global tools do not cover, such as Bangla, Nepali or Khmer.')], { spacing: { before: 120, after: 100 } }),
  src('Sources: GASA & Feedzai, Global State of Scams 2025 (Oct 2025); UNODC regional threat assessment (21 Jul 2026, via Reuters/AFP); FBI IC3 2025 Internet Crime Report (Apr 2026); DCS Computer Literacy 2024; Sunday Observer SLCERT interview (24 May 2026).'),

  // ---------- 3 solution ----------
  H1('3. Proposed solution'),
  P('One engine with three ways in. Citizens forward a message to a WhatsApp number or paste it on the web. Partner banks and telcos call the same engine through an API inside their own apps and helplines. Institutions watch a scam-wave view built from the Campaign agent. The reply always has three parts: the verdict, the reason in plain words, and what to do now.'),
  table([3200, 6438], [
    ['Root cause', 'How Rakshaka responds'],
    ['Scams arrive where nobody filters', 'Forward-to-check works for any SMS or WhatsApp message, on any network'],
    ['Messages look official', 'The Link & Sender agent checks where the message sends you, not just what it says'],
    ['Panic beats remembered advice', 'An answer in milliseconds, with one clear next step'],
    ['Awareness does not reach everyone', 'Replies in Sinhala, Tamil or English; helpline staff can check on a caller\'s behalf'],
    ['Tactics change faster than warnings', 'Drift sentinel and Campaign agent flag new waves; human review and gated retraining adapt safely'],
    ['Global tools skip local languages', 'Built for Sinhala, Tamil, English and code-mixed Singlish and Tanglish'],
  ], { boldFirst: true }),
  gap(),

  // ---------- 4 objectives ----------
  H1('4. Objectives, key features and expected outcomes'),
  H2('Objectives'),
  B('O1. Give a correct verdict, reason and next step for a suspicious message, in the user\'s language, in under one second.'),
  B('O2. Never give a false "safe": when evidence is weak, missing or conflicting, say UNCERTAIN and route the message to a human.'),
  B('O3. Show with a fair, reproducible benchmark where a multi-agent design beats a single agent, and what it costs.'),
  B('O4. Keep personal data out of every component except the one that must read it.'),
  H2('Key features'),
  table([3300, 4538, 1800], [
    ['Feature', 'What it does', 'Status'],
    ['Nine cooperating agents', 'Specialists on a shared blackboard, coordinated by an orchestrator', 'Built'],
    ['Adaptive routing', 'Link & Sender agent runs only when there is a link, number or sender ID', 'Built'],
    ['Fault tolerance', '2 s timeouts, one retry, fallbacks, degraded mode; no clearance on partial evidence', 'Built'],
    ['Privacy layer', 'NIC, card numbers and emails redacted first; traces hold redacted text only', 'Built'],
    ['Validated multilingual replies', 'Sinhala, Tamil and English templates; optional LLM rewording, rejected if it changes meaning', 'Built; native review pending'],
    ['Traces', 'JSONL record of every agent post, retry and decision', 'Built'],
    ['Human review and learning loop', 'UNCERTAIN → reviewer → labels → blocklist, gated retraining, rollback, audit log', 'Built (CLI); UI by 29 Nov'],
    ['WhatsApp channel, scam-wave view', 'Meta Cloud API webhook calling POST /check; campaign dashboard', 'Planned'],
  ], { size: 17 }),
  P([bold('Expected outcomes. '), r('For citizens: fewer clicks and payments on scam messages. For banks and telcos: lighter helpline load and earlier warning of campaigns that impersonate them. For the competition: evidence-backed answers on when multiple agents help, measured on scam catch rate, unsafe misses, false alarms, review load, latency, robustness and cost.')], { spacing: { before: 120, after: 100 } }),
  P([bold('Assumptions and constraints. '), r('All current training data is synthetic or hand-written. Confident claims about real traffic need consented, reviewed reports from a pilot partner. Sinhala and Tamil replies need native-speaker review. Users must choose to send a message; nothing is read from their phone.')]),

  // ---------- 5 multi-agent ----------
  H1('5. Multi-agent design'),
  img('architecture.png', 640, 199),
  caption('Figure 1. Agents, orchestration and human oversight (built in the repository; the WhatsApp channel and dashboard are planned).'),
  table([1700, 3700, 2338, 1900], [
    ['Agent', 'Role and responsibility', 'Capability / technique', 'Posts to blackboard'],
    ['Intake & Privacy', 'Only agent that sees raw text; redacts and parses', 'Regex redaction, URL and phone extraction, SHA-256', 'Redacted text, links, numbers, sender'],
    ['Language', 'Detects the language form and picks the reply language', 'Unicode script rules + char n-gram classifier', 'Language, reply language'],
    ['Content', 'What the words say', 'TF-IDF char + word n-grams, logistic regression', 'Risk, top words'],
    ['Tactics', 'How the message manipulates: credential or payment request, reward, threat, authority', 'Multilingual cue model; cancelled by real safety advice', 'Risk, tactic tags'],
    ['Link & Sender', 'Where the message sends you', 'Official allowlist, look-alike edit distance, shorteners, risky TLDs, sender look-alikes, blocklist', 'Risk, evidence'],
    ['Campaign', 'Known campaign or new wave?', 'Similarity to campaign centroids; memory of recent UNCERTAIN messages', 'Risk, campaign, wave size'],
    ['Drift sentinel', 'Is the wording new to the content model?', 'Unseen char n-gram share vs a validation threshold', 'Novelty flag'],
    ['Arbiter', 'Final decision and conflict resolution', 'Stacker on out-of-fold agent outputs + rules R1–R8', 'Verdict, score, rules'],
    ['Explainer', 'Reply in the user\'s language', 'Evidence-to-reason templates, optional LLM, validator', 'Validated reply'],
  ], { size: 16, boldFirst: true }),
  H2('Communication and coordination'),
  P('Agents never call each other. Each one reads a shared, thread-safe blackboard and posts a typed message (risk, confidence, evidence, data, latency, attempts). The orchestrator runs intake and language in sequence, then plans the specialists: it skips the Link & Sender agent when there is nothing to check. It runs the specialists in parallel with a 2-second timeout and one retry each, then passes the blackboard to the Arbiter and the Explainer. Every post, retry and failure is written to a JSONL trace, so a judge can replay exactly what each agent saw and said.'),
  H2('Decision-making and conflict resolution'),
  P('The Arbiter first combines Content, Tactics, Campaign and novelty with a logistic-regression stacker. The stacker is trained on out-of-fold outputs (GroupKFold by template), so it learns how far to trust each agent on unseen wording. Explicit rules then settle conflicts. A credential or payment request together with a link or number to act on is a scam pattern (R1). A look-alike domain or sender is decisive whatever the wording says (R2). An official link with no action request lowers risk (R3). A message cannot be cleared when specialists disagree strongly (R4), when the wording is novel (R5), when the Content agent failed (R6) or when the message is part of an emerging wave (R7). When a learned specialist fails, the system refuses both to clear and to accuse on partial evidence (R8).'),
  P([bold('A lesson from building it. '), r('A first stacker version learned that "any link means scam", because almost no synthetic legitimate message has a link. We removed the Link agent from the stacker and let link intelligence act only through rules R1–R4, which encode knowledge rather than a data artefact.')]),
  H2('Human oversight'),
  B('Every UNCERTAIN message goes to a review queue with redacted text and the evidence each agent found.'),
  B('Reviewer labels grow the Link agent\'s blocklist and feed retraining. A new model goes live only if it passes the regression gate (no class-recall drop above 1 point), with one-click rollback.'),
  B('The Explainer validator stops any reply that contradicts the verdict, cites evidence no agent found, or drops the line "Rakshaka never asks for your OTP, PIN or NIC".'),
  H2('Why multi-agent fits this problem'),
  P('Scam detection needs several kinds of evidence that fail independently and change at different speeds. Wording drifts monthly; look-alike domains change daily; tactics stay stable for years. Separate agents let us update one evidence source without retraining the others: a new blocklist entry or language takes effect the same day. They let the system degrade safely when one source fails, and they make each decision explainable by naming the agent that found each reason. Section 7 measures whether this pays off.'),

  // ---------- 6 technical approach ----------
  H1('6. Technical approach and implementation workflow'),
  P('Per message: intake and redaction → language → plan → five specialists in parallel → arbiter → explainer → reply. UNCERTAIN messages also go to the review queue, and every message is traced. The whole pipeline runs on one CPU in about 9–14 ms (median), with no GPU and no per-message AI fees. The Content model and synthetic data generator are reused from our earlier Rakshaka AI prototype, and this reuse is disclosed in the repository. The orchestration, all other agents, the arbiter, explainer, baseline and benchmark are new for this competition.'),
  table([1900, 7738], [
    ['Window', 'Deliverable'],
    ['16–20 Nov', 'Agents, orchestrator, arbiter, explainer, single-agent baseline, benchmark harness, traces, review → retrain → rollback loop, CI (done); this proposal'],
    ['21–24 Nov', 'Human baseline: 4 raters × 40 messages, timed. Native-speaker review of Sinhala and Tamil replies and cues. More Singlish and Tanglish data for the Language agent'],
    ['25–27 Nov', 'Review UI on our existing Streamlit desk (the review → retrain → rollback loop already works from the CLI); process-pool workers for throughput; WhatsApp webhook prototype'],
    ['28–29 Nov', 'Final benchmark run, demo video, complete project plan and risk analysis, documentation'],
    ['7 Dec', 'Final-day features added as new agents or tools on the same blackboard, with no change to existing agents'],
  ], { boldFirst: true, size: 17 }),
  gap(),

  // ---------- 7 benchmarking ----------
  H1('7. Single-agent benchmarking and evaluation'),
  H2('Fair comparison'),
  P('The single-agent baseline is one model that reads the message and decides in one pass. It uses the same training data, the same content model, the same three-way thresholds (≥0.70 SCAM, ≤0.30 LIKELY SAFE) and the same retry budget. It lacks what the multi-agent design adds. Both systems run on the same machine and the same messages through one command (python project/main.py benchmark), which writes every number to project/reports/. Nothing in the reports is edited by hand. No LLM was used in these runs.'),
  H2('Test scenarios'),
  B([bold('Held-out templates (264): '), r('synthetic messages whose wording never appears in training.')]),
  B([bold('New tactics (152): '), r('digital-ID, QR, crypto and family-impersonation lures not in training (concept drift).')]),
  B([bold('Independent set (65): '), r('hand-written Sinhala and Tanglish messages, never used for training or tuning.')]),
  B([bold('Link and sender stress set (64): '), r('impersonating links and senders, official links and real-style bank alerts. It was written while the link rules were being designed, so it is reported but is not an unbiased estimate.')]),
  B([bold('Failure injection: '), r('each agent attempt fails with probability 0.3 or 0.6, to test robustness.')]),
  H2('Metrics'),
  P('Scam caught (SCAM verdict on scams); unsafe miss (a scam called LIKELY SAFE, the most dangerous error); false alarm (a legitimate message called SCAM); review load (UNCERTAIN share, a cost in human time); latency (median and 95th percentile); throughput; compute cost per 1,000 messages; and, for humans, the same metrics plus seconds per message.'),
  H2('Results so far (generated ' + bm.generated_at.slice(0, 10) + ')'),
  img('benchmark_scam_caught.png', 600, 245),
  caption('Figure 2. Share of scams receiving a SCAM verdict. *Stress set written alongside the link rules.'),
  table([2000, 1500, 1500, 1500, 1500, 1638], [
    ['Dataset (n)', 'Unsafe miss M / S', 'False alarm M / S', 'Review load M / S', 'Median ms M / S', 'Note'],
    ...['test', 'shifted', 'independent', 'stress'].map(k => {
      const m = D[k].multi_agent, s = D[k].single_agent;
      const lab = { test: 'Held-out', shifted: 'New tactics', independent: 'Independent', stress: 'Stress*' }[k];
      const note = { test: '', shifted: 'drift', independent: 'M: 1 unsafe miss', stress: 'biased set' }[k];
      return [`${lab} (${m.n})`, `${pc(m.unsafe_miss)} / ${pc(s.unsafe_miss)}`, `${pc(m.false_alarm)} / ${pc(s.false_alarm)}`, `${pc(m.review_load)} / ${pc(s.review_load)}`, `${m.latency_p50_ms} / ${s.latency_p50_ms}`, note];
    }),
  ], { size: 16, boldFirst: true }),
  P([bold('Robustness. '), r(`At a 0.3 failure rate per attempt, the single agent gives no answer to ${pc(rob['failure_rate_0.3'].single_agent.no_answer)} of messages and the multi-agent system to ${pc(rob['failure_rate_0.3'].multi_agent.no_answer)}. The multi-agent system still catches ${pc(rob['failure_rate_0.3'].multi_agent.scam_caught)} of scams against ${pc(rob['failure_rate_0.3'].single_agent.scam_caught)}, with ${pc(rob['failure_rate_0.3'].multi_agent.false_alarm)} false alarms. At 0.6 the single agent fails to answer ${pc(rob['failure_rate_0.6'].single_agent.no_answer)} of messages; the multi-agent system answers all and sends uncertain ones to review.`)], { spacing: { before: 120, after: 100 } }),
  P([bold('Where multi-agent is worse. '), r(`It is about ${Math.round(D.test.multi_agent.latency_p50_ms / D.test.single_agent.latency_p50_ms)} times slower per message (still far below one second). It sends more messages to human review on the independent set (${pc(D.independent.multi_agent.review_load)} against ${pc(D.independent.single_agent.review_load)}). It cleared one Tanglish gift-card scam that the single agent held for review. Throughput fell from ${bm.scalability.workers_1.multi_agent_msgs_per_s} to ${bm.scalability.workers_4.multi_agent_msgs_per_s} messages/s when we added threads (Python GIL), so we will move to process workers. Compute cost is about USD ${bm.cost.multi_agent_usd_per_1000_msgs_at_full_load} per 1,000 messages on a USD 24/month server, excluding WhatsApp fees and reviewer time.`)]),
  P([bold('Transparency note. '), r('The first benchmark run showed held-out false alarms of 20.3%, all from one Sinhala water-bill template ("pay via the official app"). We added the Sinhala and Tamil equivalents of the English safety phrases "official app / office / branch" to the Tactics agent; false alarms on that set fell to 0%. Because the fix was made after seeing the test set, both runs are kept in the repository.')]),
  H2('Human baseline (planned, 21–24 Nov)'),
  P('Four raters (team members and family volunteers, including at least one older adult) will label the same 40-message blind sheet the tool generates (python project/main.py human-sheet), recording seconds per message. We will report human catch rate, unsafe misses, false alarms and time alongside both systems, with the sample size stated. No human results are claimed in this proposal.'),
  H2('Limitations, risks and ethical considerations'),
  table([2000, 7638], [
    ['Area', 'Risk and mitigation'],
    ['Data validity', 'All data is synthetic or hand-written. Results show the design works, not real-world accuracy. Mitigation: consented, reviewed reports from a pilot partner before any accuracy claim.'],
    ['Safety', 'A false "safe" can cost a victim money. Mitigation: rules R4–R8 forbid clearance on weak, novel, conflicting or missing evidence; unsafe misses are the primary metric.'],
    ['Bias and fairness', 'Language quality is uneven: Sinhala and Tanglish have higher review load, and some Singlish is mislabelled as Tanglish. Mitigation: per-language reporting, native-speaker review, more data for weak languages.'],
    ['Privacy', 'Messages can contain NIC numbers, card numbers and names. Mitigation: only the Intake agent sees raw text; redaction first; hash-only identity; redacted traces and review queue; PDPA impact assessment before any pilot.'],
    ['Reliability', 'Agents can fail or slow down. Mitigation: timeouts, retries, fallbacks and degraded mode; failure-injection tests in the benchmark.'],
    ['Misuse and trust', 'Scammers could probe the checker or imitate the bot. Mitigation: rate limits; a verified business account; every reply says Rakshaka never asks for an OTP, PIN or NIC.'],
    ['Accountability', 'An optional LLM may only reword replies, never decide, and its output is validated. All AI tools used in development are declared in docs/PROJECT_DETAILS.md.'],
  ], { boldFirst: true, size: 17 }),
  gap(),

  // ---------- 8 tech ----------
  H1('8. Technologies, frameworks and tools'),
  table([2600, 4438, 2600], [
    ['Layer', 'Choice', 'Alternatives considered'],
    ['Language, runtime', 'Python 3.12+, CPU only; standard-library thread pools and HTTP server', 'Agent frameworks (LangGraph, AutoGen): add LLM dependency and cost per message'],
    ['Learned agents', 'scikit-learn: TF-IDF, logistic regression, GroupKFold', 'Multilingual transformers (XLM-R): more accurate with real data, but need a GPU and larger data'],
    ['Link intelligence', 'Official-domain allowlist, edit distance, blocklist from reviews', 'Google Web Risk API: planned addition (free tier up to 100k calls/month)'],
    ['Explanations', 'Templates + validator; optional Anthropic Messages API for rewording', 'LLM-only replies: risk of contradicting the verdict'],
    ['Pre-existing prototype (reused)', 'FastAPI, Streamlit review desk, Docker, GitHub Actions CI', '—'],
    ['Channel (planned)', 'Meta WhatsApp Cloud API webhook calling POST /check', 'SMS short code via a telco (later)'],
    ['Dependencies', 'scikit-learn, NumPy, SciPy, joblib, requests (all permissive licences)', '—'],
  ], { size: 17, boldFirst: true }),
  gap(),
  H1('References'),
  ...[
    'Global Anti-Scam Alliance & Feedzai, Global State of Scams 2025 Report (Oct 2025).',
    'UNODC regional threat assessment on transnational organised crime in Southeast Asia (21 Jul 2026), via Reuters, AFP and OCCRP.',
    'FBI Internet Crime Complaint Center, 2025 IC3 Annual Report (Apr 2026); AARP summary.',
    'CBSL Governor, "Be Scam Proof" keynote (2 Jun 2026); CBSL Payments Bulletin Q1 2026.',
    'Sunday Times, "CERT records over 12,000 complaints in 2025" (1 Jan 2026); Ada Derana (3 Jun, 11 Sep 2026); Sunday Observer SLCERT interview (24 May 2026).',
    'Department of Census and Statistics: Census of Population and Housing 2024; Computer Literacy 2024. Department of Pensions statistics (Feb 2025). DataReportal Digital 2026: Sri Lanka.',
    '2026 scam warnings from SLCERT, Sri Lanka Post, DRP, Police and the Welfare Benefits Board (Newswire, Newsfirst, Ada Derana); Daily Mirror (24 Nov 2025).',
    'ScamShield (scamshield.org.sg) and Open Government Products metrics.',
    'Byte Benders, Rakshaka AI prototype (Oct 2026), github.com/geemalfernando/Rakshaka_AI (reused components, disclosed).',
  ].map(t => new Paragraph({ numbering: { reference: 'n', level: 0 }, spacing: { after: 40 }, children: [r(t, { size: 17 })] })),
];

const doc = new Document({
  creator: 'Byte Benders', title: 'Rakshaka AI – AI Catalyst 2026 Proposal',
  styles: {
    default: { document: { run: { font: 'Arial', size: 20 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: 'Arial', size: 28, bold: true, color: NAVY }, paragraph: { spacing: { before: 260, after: 110 }, keepNext: true, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: 'Arial', size: 22, bold: true, color: '333333' }, paragraph: { spacing: { before: 140, after: 70 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [
    { reference: 'b', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 400, hanging: 240 } } } }] },
    { reference: 'n', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 400, hanging: 300 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1000, bottom: 1000, left: 1134, right: 1134 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [r('Rakshaka AI · Byte Benders · Innodata AI Catalyst 2026', { size: 16, color: GREY })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [r('Page ', { size: 16, color: GREY }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: GREY }), r(' of ', { size: 16, color: GREY }), new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16, color: GREY })] })] }) },
    children: body,
  }],
});
Packer.toBuffer(doc).then(b => fs.writeFileSync(require('path').join(__dirname, '../../') + 'docs/Proposal.docx', b));
