# Submitting AIR/1 as an IETF Internet-Draft

This document takes `draft-air-agent-intent-receipt-00` from "written" to
"one click from submitted." Everything here is mechanical; the only step that
needs a human is pressing **Submit** on the IETF Datatracker (and, if this is a
brand-new draft name, replying to the confirmation email).

## 0. Current readiness

| Precondition | State |
| --- | --- |
| Spec compiles to submittable formats | DONE — `xml2rfc` renders `.xml` to both `.txt` (27 KB) and `.html` (82 KB) with no errors |
| Open-source reference implementation | DONE — `air_federation_verifier` (dependency-free) plus the SDK's signer/verifier |
| >=2 independent federation nodes agree | DONE — two nodes on different Base RPC operators return byte-identical valid verdicts |
| Draft metadata valid | DONE — `category="std"`, `submissionType="IETF"`, `ipr="trust200902"`, `consensus="true"`, `version="3"` |

The three preconditions the objective set (compilable spec, open
implementation, >=2-node consensus) are all in place.

## 1. What the Datatracker requires at upload

The submission tool at <https://datatracker.ietf.org/submit/> accepts a draft
in either of two ways:

1. **XML only** (preferred) — upload `draft-air-agent-intent-receipt-00.xml`.
   The Datatracker runs `xml2rfc` server-side and generates the text/HTML/PDF
   renderings itself. This is why a clean local `xml2rfc` run is the real
   gate: if it renders here, it renders there.
2. **Text + XML** — upload the pre-rendered `.txt` alongside the `.xml`.

Requirements the file must satisfy, and our status:

- Filename matches `docName` and ends in `-00`. OK
  (`draft-air-agent-intent-receipt-00`).
- Draft name uses only lowercase, digits, and hyphens. OK.
- Version is exactly two digits. OK (`00`).
- `<seriesInfo name="Internet-Draft" .../>` present. OK.
- Boilerplate/IPR: `ipr="trust200902"` is the current accepted value. OK.
- Renders under `xml2rfc` with no fatal errors. OK (verified locally).

## 2. Known idnits notes (warnings, not blockers)

The Datatracker runs `idnits` and shows warnings but still lets you submit.
Two cosmetic items in `-00`:

- `<date/>` is empty. The Datatracker stamps it with the actual upload date,
  which is the recommended way to avoid a stale hard-coded date. Leave as is.
- Author email is the placeholder `spec@example.org`. idnits flags placeholder
  example.org addresses. This does not block submission, but before the draft
  is meant to be taken seriously the editor should set a real
  `<organization>` and `<email>`. This is a one-line edit in the `<author>`
  block and is the only content change worth making pre-submit.

Nothing above stops an upload today; the email is the only thing worth fixing
first if you want a clean idnits run.

## 3. Exact submission procedure

Prerequisites (human, one-time):

1. An IETF Datatracker account: <https://datatracker.ietf.org/accounts/create/>.
   Free, email-verified. No working-group membership needed to submit an
   individual draft.

Upload:

2. Go to <https://datatracker.ietf.org/submit/>.
3. Upload `spec/draft-air-agent-intent-receipt-00.xml`.
4. The tool renders and runs idnits, then shows a confirmation page listing the
   document name, revision `00`, and the authors it parsed from the XML.
5. Because this is the first version of a new draft name, the Datatracker
   emails each listed author an approval link. The submission is not posted
   until one author clicks it. (With a real author email in the XML, this lands
   in your inbox; with the placeholder it will not arrive, which is the second
   reason to set a real address before submitting.)
6. After confirmation the draft is public at
   `https://datatracker.ietf.org/doc/draft-air-agent-intent-receipt/` and gets
   an announcement to the i-d-announce list automatically.

## 4. I-D cutoff timing

Internet-Draft submission closes for about two weeks around each IETF meeting
(from the Monday before the meeting until the Monday after). Outside those
windows submission is open year-round. Individual drafts (not tied to a
working-group session) are only affected by the hard cutoff during the meeting
blackout; there is no benefit to rushing against a WG deadline here. Check the
current window at <https://datatracker.ietf.org/meeting/important-dates/>
before submitting; if we are inside a blackout, wait for it to reopen.

## 5. Pre-submit checklist (do these, then submit)

- [ ] Set a real `<organization>` and `<email>` in the `<author>` block of the
      `.xml` (replaces `spec@example.org`). Only content edit needed.
- [ ] Re-run `xml2rfc draft-air-agent-intent-receipt-00.xml --text --html` and
      confirm no errors. (Automated in `spec/build.ps1` / documented below.)
- [ ] Create/confirm an IETF Datatracker account.
- [ ] Confirm we are not inside an IETF meeting I-D blackout.
- [ ] Upload the `.xml` at the submit URL and click through the confirmation
      email. (This is the single irreversible "publish" action.)

## 6. Local build command

From `spec/`, using any environment with `xml2rfc` installed
(`pip install xml2rfc`):

```
xml2rfc draft-air-agent-intent-receipt-00.xml --text --html
```

This produces `draft-air-agent-intent-receipt-00.txt` and `.html`, the same
renderings the Datatracker will generate. A clean run here is the gate that
proves the upload will render there.

## 7. Draft announcement (ready to send once posted)

> Subject: New Internet-Draft: AIR/1 — Offline-Verifiable Agent Intent Receipts over x402
>
> I've submitted a new individual Internet-Draft,
> draft-air-agent-intent-receipt-00, "AIR/1: Offline-Verifiable Agent Intent
> Receipts over x402."
>
> An Agent Intent Receipt is a self-certifying record that an HTTP request was
> fulfilled by a named provider and paid for on-chain over the x402 payment
> protocol. The receipt can be verified offline by any party, without trusting
> the issuer and without access to the issuer's systems. The draft defines the
> object model, a canonical JSON serialization, an extensible signature-suite
> framework (with initial suites for secp256k1/EVM and Ed25519/Solana), the
> verification procedure, and an IANA registry for the suites.
>
> There is an open-source, dependency-free reference verifier, and the scheme
> has been checked by two independent federation nodes running on different
> chain RPC operators that reach byte-identical verdicts on the same receipt.
>
> Draft: https://datatracker.ietf.org/doc/draft-air-agent-intent-receipt/
> Feedback welcome.
