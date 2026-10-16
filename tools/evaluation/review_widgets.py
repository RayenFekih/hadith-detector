"""ipywidgets presentation only; persistence and validation live in ReviewSession."""

import html
import json

import ipywidgets as W

from .pipeline import CONFIGURATIONS
from .review import CASE_LABELS, INTENTS
from .review_notebook import EvidenceBrowser, highlighted


def escaped(value):
    return html.escape(str(value))


CLASSIFICATIONS = {
    "intended_quotation": (
        "Intended Hadith quotation",
        "The writer is quoting a Hadith. Check that the highlighted words are the "
        "intended quotation and its boundaries are right.",
    ),
    "not_intended_quotation": (
        "Not intended",
        "These words are not being used as a Hadith quotation here. Check the surrounding "
        "paragraph; similar words in a source do not by themselves mean a quotation.",
    ),
    "incidental_chain": (
        "Incidental narrator chain",
        "The highlighted words name narrators or a transmission chain. Check whether they "
        "are incidental here rather than an intended quotation.",
    ),
    "quranic_wording": (
        "Quranic wording",
        "The highlighted words are Quranic wording in this context. Check that they are "
        "being used as Quranic text rather than as a Hadith quotation.",
    ),
    "uncertain": (
        "Uncertain",
        "The proposal has no confident classification yet. Choose Correct if you can "
        "supply one, or Uncertain if you also cannot decide.",
    ),
    "out_of_corpus": (
        "Outside the available collections",
        "This may be a quotation outside the Bukhari/Muslim corpus. Check the context; "
        "no detection alone does not establish that a quotation is absent or outside it.",
    ),
    "contains_quotation": (
        "Contains a Hadith quotation",
        "Read the whole paragraph and check whether it contains at least one intended "
        "Hadith quotation. You will review individual highlighted passages separately.",
    ),
    "quotation_free": (
        "No intended Hadith quotation",
        "Read the whole paragraph and check that none of it is intended as a Hadith "
        "quotation, including quotations the suggestions may have missed.",
    ),
}

DECISION_HELP = (
    "<p><b>Accept</b> — the proposed label and boundaries are right.<br>"
    "<b>Correct</b> — keep this item but fix its label or boundaries. "
    "For example, change a supposed quotation to <i>Not intended</i>.<br>"
    "<b>Reject</b> — discard an unusable proposal, such as a fragment that cannot "
    "be meaningfully classified. A false alarm with a valid span can be corrected "
    "to <i>Not intended</i>; it does not need rejection.<br>"
    "<b>Uncertain</b> — you cannot confidently decide; explain why if you can.</p>"
)

REVIEW_EXAMPLES = (
    "<h4>Three examples</h4>"
    "<p><b>1. Accept:</b> The label says <i>Intended Hadith quotation</i>, "
    "and the writer clearly quotes the highlighted passage with the right boundaries.</p>"
    "<p><b>2. Correct:</b> The label says <i>Intended Hadith quotation</i>, but the words "
    "are ordinary prose here. Choose Correct, then <i>Not intended</i>. "
    "If the proposal already says Not intended and you agree, choose Accept.</p>"
    "<p><b>3. Reject or Uncertain:</b> Reject an unusable fragment that cannot be "
    "meaningfully assessed. If the span is meaningful but its intent is unclear, "
    "choose Uncertain instead. If its boundaries can be repaired, use Correct.</p>"
    "<p>Paragraph review asks about the whole text; highlighted-passage review asks "
    "only about the marked words. Source similarity does not prove quotation intent "
    "or independently authenticate a Hadith. All decisions remain drafts.</p>"
)


class ReviewWidget:
    def __init__(self, session):
        self.session = session
        self.evidence = EvidenceBrowser(session)
        self.loading = False
        self.history = []
        self.heading = W.HTML()
        self.paragraph = W.HTML()
        self.description = W.HTML()
        self.question = W.HTML("<h3>Is this proposed classification correct?</h3>")
        self.decision_help = W.HTML(DECISION_HELP)
        self.message = W.HTML()
        self.group = W.Dropdown(
            options=["all", "corpus_derived", "natural_text"], description="Group"
        )
        self.kind = W.Dropdown(options=["all", "case", "span"], description="Row type")
        self.status = W.Dropdown(
            options=["pending", "all", "accept", "correct", "reject", "uncertain"],
            description="Status",
        )
        self.jump_id = W.Text(placeholder="N0005 or N0005:span:3", description="Jump to")
        jump = W.Button(description="Go")
        jump.on_click(lambda _: self.guard(self.jump))
        self.decision = W.ToggleButtons(
            options=[
                ("Accept", "accept"),
                ("Correct", "correct"),
                ("Reject", "reject"),
                ("Uncertain", "uncertain"),
            ],
            value=None,
            description="",
            style={"button_width": "115px"},
        )
        self.classification = W.Dropdown(description="Class", layout=W.Layout(width="95%"))
        self.start = W.Text(description="Start", placeholder="Python character offset")
        self.end = W.Text(description="End", placeholder="Exclusive end offset")
        self.refs = W.Textarea(
            description="References",
            placeholder="Semicolon-separated Hadith keys; blank = inherit",
            layout=W.Layout(width="95%", height="65px"),
        )
        self.notes = W.Textarea(description="Notes", layout=W.Layout(width="95%", height="75px"))
        self.boundary_details = W.Accordion(
            children=[
                W.VBox(
                    [
                        W.HTML(
                            "Optional: change quotation boundaries or references. "
                            "Leave blank to keep the proposal. Check the preview after editing."
                        ),
                        W.HBox([self.start, self.end]),
                        self.refs,
                    ]
                )
            ],
            selected_index=None,
        )
        self.boundary_details.set_title(0, "Adjust boundaries or references (optional)")
        self.correction = W.VBox([self.classification, self.boundary_details])
        self.preview = W.HTML()
        self.decision.observe(self.toggle_correction, "value")
        self.start.observe(self.preview_correction, "value")
        self.end.observe(self.preview_correction, "value")
        buttons = []
        for label, action in [
            ("Save & Next", self.save_next),
            ("Previous", self.previous),
            ("Skip", self.skip),
            ("Save Progress", self.save_current),
        ]:
            button = W.Button(description=label, button_style="primary" if not buttons else "")
            button.on_click(lambda _, action=action: self.guard(action))
            buttons.append(button)
        self.save_next_button = buttons[0]
        self.config_details = W.Accordion(children=[W.HTML()], selected_index=None)
        self.config_details.set_title(0, "Configurations and provenance")
        self.evidence_config = W.Dropdown(options=list(CONFIGURATIONS), description="Config")
        self.detection = W.Dropdown(description="Detection")
        self.ref_search = W.Text(
            description="Find key", placeholder="Filter complete reference list"
        )
        self.ref_page = W.IntText(value=1, description="Page (100)")
        self.ref_choice = W.Dropdown(description="Reference", layout=W.Layout(width="95%"))
        self.ref_count = W.HTML()
        self.ref_detail = W.HTML()
        evidence_box = W.VBox(
            [
                W.HTML("Complete saved evidence; each configuration retains its own occurrences."),
                self.evidence_config,
                self.detection,
                self.ref_search,
                self.ref_page,
                self.ref_count,
                self.ref_choice,
                self.ref_detail,
            ]
        )
        self.evidence_panel = W.Accordion(children=[evidence_box], selected_index=None)
        self.evidence_panel.set_title(0, "Supporting references — expand to load details")
        self.evidence_panel.observe(lambda _: self.guard(self.load_evidence), "selected_index")
        self.evidence_config.observe(lambda _: self.guard(self.load_evidence), "value")
        self.detection.observe(lambda _: self.guard(self.list_refs), "value")
        self.ref_search.observe(lambda _: self.guard(self.list_refs), "value")
        self.ref_page.observe(lambda _: self.guard(self.list_refs), "value")
        self.ref_choice.observe(lambda _: self.guard(self.show_reference), "value")
        self.manual_start = W.IntText(description="Start", value=0)
        self.manual_end = W.IntText(description="End", value=1)
        self.manual_intent = W.Dropdown(
            options=[(CLASSIFICATIONS[value][0], value) for value in sorted(INTENTS)],
            value="intended_quotation",
            description="Class",
            layout=W.Layout(width="95%"),
        )
        self.manual_refs = W.Textarea(description="References", layout=W.Layout(width="95%"))
        self.manual_notes = W.Textarea(description="Notes", layout=W.Layout(width="95%"))
        self.manual_preview = W.HTML()
        self.manual_start.observe(self.preview_manual, "value")
        self.manual_end.observe(self.preview_manual, "value")
        add = W.Button(description="Add & Save quotation", layout=W.Layout(width="220px"))
        add.on_click(lambda _: self.guard(self.add_manual))
        self.manual_panel = W.Accordion(
            children=[
                W.VBox(
                    [
                        W.HTML(
                            "Add a missed quotation in the current case. "
                            "This saves a human correction, "
                            "not an automatically accepted proposal. Save current edits first."
                        ),
                        W.HBox([self.manual_start, self.manual_end]),
                        self.manual_preview,
                        self.manual_intent,
                        self.manual_refs,
                        self.manual_notes,
                        add,
                    ]
                )
            ],
            selected_index=None,
        )
        self.manual_panel.set_title(0, "Add a quotation missed by every configuration")
        for widget in (self.group, self.kind, self.status):
            widget.observe(lambda _: self.guard(self.filter_changed), "value")
        self.item_details = W.HTML()
        self.advanced = W.Accordion(
            children=[W.VBox([self.item_details, self.evidence_panel, self.config_details])],
            selected_index=None,
        )
        self.advanced.set_title(0, "Advanced Details — sources and technical evidence")
        self.navigation = W.Accordion(
            children=[
                W.VBox(
                    [
                        W.HBox(
                            [self.group, self.kind, self.status],
                            layout=W.Layout(flex_flow="row wrap"),
                        ),
                        W.HBox([self.jump_id, jump]),
                    ]
                )
            ],
            selected_index=None,
        )
        self.navigation.set_title(0, "Find or filter review items")
        self.help = W.Accordion(children=[W.HTML(REVIEW_EXAMPLES)], selected_index=None)
        self.help.set_title(0, "How to decide — three examples")
        self.widget = W.VBox(
            [
                W.HTML(
                    "<h2>Review the Arabic text</h2>"
                    "<p>Read, check the proposed label, choose a decision, "
                    "then Save &amp; Next.</p>"
                ),
                self.heading,
                self.paragraph,
                self.description,
                self.question,
                self.decision_help,
                self.decision,
                self.correction,
                self.preview,
                self.notes,
                self.save_next_button,
                self.message,
                W.HBox(buttons[1:]),
                self.help,
                self.manual_panel,
                self.navigation,
                self.advanced,
                W.HTML(
                    "<small>Previous visits review history. Skip discards unsaved form edits. "
                    "Jump clears filters. Save Progress saves this form without moving.</small>"
                ),
            ],
            layout=W.Layout(max_width="1100px", width="100%"),
        )
        self.render()

    def _ipython_display_(self):
        from IPython.display import display

        display(self.widget)

    def guard(self, action):
        if self.loading:
            return
        try:
            action()
        except Exception as error:
            self.message.value = '<p style="color:#b22">' + escaped(error) + "</p>"

    def filters(self):
        return dict(group=self.group.value, kind=self.kind.value, status=self.status.value)

    def render(self):
        self.loading = True
        try:
            row = self.session.row
            done, total = self.session.progress
            self.heading.value = f"<h3>{done} / {total} reviewed</h3>"
            if row is None:
                self.paragraph.value = "No items in this filter. Change status to all to revisit."
                self.description.value = self.preview.value = ""
                self.decision.disabled = True
                self.question.layout.display = self.decision_help.layout.display = "none"
                self.correction.layout.display = "none"
                self.notes.disabled = True
                self.config_details.selected_index = None
                self.evidence_panel.selected_index = None
                self.manual_panel.selected_index = None
                self.advanced.selected_index = None
                return
            self.decision.disabled = False
            self.question.layout.display = self.decision_help.layout.display = ""
            self.notes.disabled = False
            is_case = row["row_kind"] == "case"
            title = "Whole-paragraph review" if is_case else "Highlighted-passage review"
            instruction = (
                "Read the entire paragraph. "
                "Decide whether it contains an intended Hadith quotation."
                if is_case
                else "Review the highlighted words. "
                "Use the surrounding paragraph to judge their intent."
            )
            color = "#1e5672" if is_case else "#78540b"
            self.heading.value += (
                f'<div style="border-left:5px solid {color};padding:8px 14px">'
                f"<b>{title}</b><br>{instruction}</div>"
            )
            # Manual additions have corrected offsets, with no original proposal span.
            start = row["span_start"] or row["corrected_start"]
            end = row["span_end"] or row["corrected_end"]
            a = int(start) if start else None
            b = int(end) if end else None
            self.paragraph.value = highlighted(row["input_text"], a, b)
            label = (
                row["proposed_case_label"]
                if is_case
                else row["proposed_intent"] or row["corrected_intent"] or "uncertain"
            )
            friendly_label, explanation = CLASSIFICATIONS[label]
            self.description.value = (
                '<div style="padding:12px 0">'
                f'<div style="font-size:21px"><b>Proposed: {escaped(friendly_label)}</b></div>'
                f"<p>{escaped(explanation)}</p></div>"
            )
            self.item_details.value = (
                "<pre style='white-space:pre-wrap'>"
                + escaped(
                    "\n".join(
                        f"{key}: {row[key]}"
                        for key in (
                            "proposal_id",
                            "case_id",
                            "group",
                            "row_kind",
                            "decision",
                            "corpus_support",
                            "uncertainty_flags",
                            "proposal_notes",
                            "span_start",
                            "span_end",
                            "span_text",
                        )
                    )
                )
                + "</pre>"
            )
            options = CASE_LABELS if is_case else INTENTS
            self.classification.options = [
                ("No classification correction", ""),
                *[(CLASSIFICATIONS[value][0], value) for value in sorted(options)],
            ]
            self.classification.value = row[
                "corrected_case_label" if is_case else "corrected_intent"
            ]
            self.start.value, self.end.value = row["corrected_start"], row["corrected_end"]
            self.start.disabled = self.end.disabled = is_case
            self.refs.value, self.notes.value = row["corrected_references"], row["reviewer_notes"]
            self.decision.value = row["decision"] or None
            self.config_details.children[0].value = (
                "<pre style='white-space:pre-wrap'>"
                + escaped(
                    "\n".join(
                        f"{key}: {row[key]}"
                        for key in (
                            "configurations",
                            "config_costs",
                            "default_comparison",
                            "evidence_ids",
                            "source_url",
                            "source_revision",
                            "source_license",
                            "source_attribution",
                        )
                    )
                )
                + "</pre>"
            )
            self.evidence_panel.selected_index = None
            available = row["configurations"].split(";")
            self.evidence_config.value = (
                "m5-e0-o0"
                if "m5-e0-o0" in available
                else available[0]
                if available[0]
                else "m5-e0-o0"
            )
            self.ref_detail.value = ""
            self.ref_search.value = ""
            self.ref_page.value = 1
            self.manual_panel.selected_index = None
            self.advanced.selected_index = None
            self.config_details.selected_index = None
            self.boundary_details.selected_index = None
            self.message.value = ""
        finally:
            self.loading = False
        self.toggle_correction()
        self.preview_manual()

    def toggle_correction(self, *_):
        self.correction.layout.display = "" if self.decision.value == "correct" else "none"
        self.notes.layout.display = (
            "" if self.decision.value in ("correct", "uncertain") or self.notes.value else "none"
        )
        self.preview_correction()

    def preview_correction(self, *_):
        if self.loading:
            return
        self.preview.value = ""
        row = self.session.row
        if row and self.decision.value == "correct" and row["row_kind"] == "span":
            try:
                a = int(self.start.value or row["span_start"])
                b = int(self.end.value or row["span_end"])
                self.preview.value = "<p>Corrected preview:</p>" + highlighted(
                    row["input_text"], a, b
                )
            except (ValueError, TypeError):
                self.preview.value = "Supply valid start and end offsets to preview."

    def preview_manual(self, *_):
        if self.loading or self.session.row is None:
            return
        try:
            self.manual_preview.value = highlighted(
                self.session.row["input_text"], self.manual_start.value, self.manual_end.value
            )
        except ValueError:
            self.manual_preview.value = "Offsets must select a nonempty original-text slice."

    def form_changes(self):
        row = self.session.row
        if row is None:
            return {}
        return dict(
            decision=self.decision.value or "",
            reviewer_notes=self.notes.value,
            corrected_case_label=self.classification.value if row["row_kind"] == "case" else "",
            corrected_intent=self.classification.value if row["row_kind"] == "span" else "",
            corrected_start=self.start.value,
            corrected_end=self.end.value,
            corrected_references=self.refs.value.strip(),
        )

    def require_saved(self):
        row = self.session.row
        if row is None:
            return
        changes = self.form_changes()
        if changes["decision"] != "correct":
            for name in (
                "corrected_case_label",
                "corrected_intent",
                "corrected_start",
                "corrected_end",
                "corrected_references",
            ):
                changes[name] = ""
        if any(row[key] != value for key, value in changes.items()):
            raise ValueError("Unsaved edits: use Save Progress, Save & Next, or Skip to discard")

    def save_current(self):
        if self.session.row is None:
            self.session.save()
        else:
            self.session.update(**self.form_changes())
        self.render()
        self.message.value = "<p>Progress saved atomically. Drafts remain unapproved.</p>"

    def save_next(self):
        old = self.session.current
        before = [r["proposal_id"] for r in self.session.visible(**self.filters())]
        self.save_current()
        if old:
            self.history.append(old)
        after = {r["proposal_id"] for r in self.session.visible(**self.filters())}
        index = before.index(old) if old in before else -1
        ordered = before[index + 1 :] + before[: index + 1]
        self.session.current = next((identity for identity in ordered if identity in after), None)
        self.render()

    def skip(self):
        if self.session.current:
            self.history.append(self.session.current)
        self.session.move(**self.filters())
        self.render()

    def previous(self):
        self.require_saved()
        if self.history:
            self.session.current = self.history.pop()
            self.set_all_filters()
        else:
            self.session.move(-1, **self.filters())
        self.render()

    def set_all_filters(self):
        self.loading = True
        self.group.value = self.kind.value = self.status.value = "all"
        self.loading = False

    def jump(self):
        self.require_saved()
        self.session.jump(self.jump_id.value.strip())
        self.set_all_filters()
        self.render()

    def filter_changed(self):
        self.require_saved()
        visible = self.session.visible(**self.filters())
        self.session.current = visible[0]["proposal_id"] if visible else None
        self.render()

    def add_manual(self):
        self.require_saved()
        row = self.session.row
        if row is None:
            raise ValueError("Jump to a case before adding a quotation")
        self.session.add_span(
            row["case_id"],
            self.manual_start.value,
            self.manual_end.value,
            self.manual_intent.value,
            self.manual_refs.value.strip(),
            self.manual_notes.value,
        )
        self.set_all_filters()
        self.render()
        self.message.value = "Manual quotation saved. Revisit its correction fields to adjust it."

    def load_evidence(self):
        if self.evidence_panel.selected_index is None or self.session.row is None:
            return
        row = self.session.row
        matches = self.evidence.get(row["case_id"], self.evidence_config.value)
        choices = [
            (f"[{d['start']}, {d['end']}) · {len(d['references'])} references", i)
            for i, d in enumerate(matches)
            if row["row_kind"] == "case"
            or (str(d["start"]), str(d["end"])) == (row["span_start"], row["span_end"])
        ]
        self.loading = True
        self.detection.options = choices
        self.detection.value = choices[0][1] if choices else None
        self.loading = False
        self.list_refs()

    def list_refs(self):
        if self.evidence_panel.selected_index is None or self.session.row is None:
            return
        row = self.session.row
        self.active_references = []
        if self.detection.value is not None:
            match = self.evidence.get(row["case_id"], self.evidence_config.value)[
                self.detection.value
            ]
            self.active_references = match["references"]
        refs = [
            (ref["record"]["hadith_key"], i)
            for i, ref in enumerate(self.active_references)
            if self.ref_search.value.strip() in ref["record"]["hadith_key"]
        ]
        page = max(1, self.ref_page.value)
        self.loading = True
        self.ref_choice.options = refs[(page - 1) * 100 : page * 100]
        page_refs = list(self.ref_choice.options)
        self.ref_choice.value = page_refs[0][1] if page_refs else None
        self.loading = False
        union = self.evidence.references(row)
        self.ref_count.value = (
            f"{len(refs)} filtered / {len(self.active_references)} in this configuration. "
            f"{len(union)} supporting identities across configurations. Page {page}."
        )
        if not self.active_references:
            self.ref_count.value += (
                "<p>No saved detection for this span/configuration. "
                "Try another configuration. "
                "Input-first proposals may have no detector evidence.</p>"
                "<details><summary>Known source identities (full union)</summary><pre>"
                + escaped("\n".join(union))
                + "</pre></details>"
                "<details><summary>Original source context / provenance (not alignment evidence)"
                "</summary>" + highlighted(row["source_context"]) + "</details>"
            )
        self.show_reference()

    def show_reference(self):
        self.ref_detail.value = ""
        if self.ref_choice.value is None:
            return
        ref = self.active_references[self.ref_choice.value]
        record = ref["record"]
        body = f"<h4>{escaped(record['hadith_key'])}</h4>"
        body += "<details><summary>Complete source narration</summary>"
        body += highlighted(record["text"]) + "</details>"
        for occurrence in ref["occurrences"]:
            a, b = occurrence["start"], occurrence["end"]
            body += (
                f"<details><summary>Source [{a}, {b}) · edits {occurrence['errors']} · "
                f"omissions {occurrence['missing_words']}</summary>"
                + highlighted(record["text"], a, b)
                + "<details><summary>Full alignment and omitted-token details</summary><pre "
                "style='white-space:pre-wrap'>"
                + escaped(json.dumps(occurrence, ensure_ascii=False, indent=2))
                + "</pre></details></details>"
            )
        metadata = {k: v for k, v in record.items() if k != "text"}
        body += (
            "<details><summary>All source metadata / URL</summary>"
            "<pre style='white-space:pre-wrap'>"
            + escaped(json.dumps(metadata, ensure_ascii=False, indent=2))
            + "</pre></details>"
        )
        self.ref_detail.value = body
