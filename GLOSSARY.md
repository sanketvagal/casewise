# casewise

Safety-first triage of support tickets for a fictional clinical practice-management product. Each ticket is auto-replied from the knowledge base or escalated to a human, and the evaluation measures how well those decisions are made.

## Triage

**Ticket**:
One support request from a clinic, made up of a subject, a body and metadata such as the requester's role.

**Auto-reply**:
A triage decision to answer the ticket directly with a draft that cites one knowledge-base article.
_Avoid_: Deflection (deflection is a metric, not a decision), answer

**Escalation**:
A triage decision to hand the ticket to a human agent, with a reason and a handoff packet. Once a ticket is escalated, nothing can turn it back into an auto-reply.
_Avoid_: Handoff (the handoff packet is what comes with an escalation)

**Escalation reason**:
The rule identifier or failed check that caused an escalation.

**Safety rule**:
A deterministic condition, with a stable identifier, that forces an escalation before any model decision.

**Intent**:
The topic a ticket is asking about, chosen from a fixed set of labels.

**Handoff packet**:
What a human agent receives with an escalation: the reason, the detected intent, the top retrieved articles, a draft for human review and a suggested next step.

## Evaluation

**Labeled ticket**:
A ticket paired with its known-correct answers: intent, answering article (or none), must-escalate and escalation reason.

**Answering article**:
The labeled knowledge-base article that truly answers a ticket, or none. It is the source article the judge compares a reply against.
_Avoid_: Source article (use only when quoting the spec), expected article

**Must-escalate**:
A label that is true when a safety rule applies to the ticket or no article answers it. It is the ground truth for whether a ticket should be escalated.

**Expected escalation reason**:
The labeled reason a must-escalate ticket should escalate: a safety rule identifier, or `no_answer` when the knowledge base doesn't cover the ticket.

**Correct auto-reply**:
An auto-reply on a ticket that is not must-escalate, whose cited article is the answering article, and which the judge marks correct.
_Avoid_: Accurate reply, good reply

**Judge**:
A model from a different family from triage. It decides whether an auto-reply answers the ticket's question, agrees with the answering article and adds nothing the article doesn't support.

**Unjudged**:
An auto-reply the judge could not produce a valid verdict for. It counts as incorrect.

**Deflection rate**:
Correct auto-replies divided by all tickets. A wrong auto-reply is a failure, not a deflection.

**Answer accuracy**:
Correct auto-replies divided by all auto-replies.

**Unsafe auto-reply**:
An auto-reply on a must-escalate ticket. The target count is zero.

**Escalation recall**:
Escalations on must-escalate tickets divided by all must-escalate tickets, whatever path caused the escalation. The target is 100%.

## Data generation

**Topic**:
One specific support question or problem from the product spec, such as moving an appointment to another provider. Each topic belongs to one product area.

**Product spec**:
The generated description of the fictional product: a summary and about 40 topics across six product areas.

**Covered topic**:
A topic the knowledge base has an article for. Its article id is the topic id.

**Simulated gap**:
A topic the initial knowledge base deliberately doesn't cover. Gaps are chosen at random during generation and recorded only for scoring. Triage and insights never see them.
_Avoid_: Planted gap, missing article (that is what the insights report infers, not what it is told)

**Labels first**:
Generation order in which every ticket's labels are sampled and saved before a model writes its text from them.

**Safety situation**:
What a rule-labeled ticket is written about, such as a prescription sent to the wrong pharmacy. It is described in plain words, never with the rule's phrases.

**Weeks 1–2, weeks 3–4**:
The two fortnights the tickets are split into by timestamp. Tuning and gap-finding use only weeks 1–2. Weeks 3–4 are held out.
