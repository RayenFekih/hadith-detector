"""One input screen, original passages and two simple technical judgments per span."""

import copy
import html
import json

import ipywidgets as W

from .pipeline import CONFIGURATIONS, DEFAULT
from .review_notebook import highlighted

GROUP_LABELS = {
    "exact": "Controlled example — exact Hadith excerpt",
    "fuzzy": "Controlled example — modified Hadith excerpt",
    "natural": "General Arabic prose",
    "commentary": "Religious commentary",
}


def marked(text, ranges, *, omitted=False):
    """Escape unchanged text; overlap changes display color only, never stored spans."""
    for a, b in ranges:
        if not 0 <= a < b <= len(text):
            raise ValueError("Highlight outside original text")
    points = sorted({0, len(text), *(p for r in ranges for p in r)})
    parts = []
    for a, b in zip(points, points[1:], strict=False):
        piece = html.escape(text[a:b])
        if any(start <= a and b <= end for start, end in ranges):
            color = "#ffd4db" if omitted else "#ffe28a"
            piece = f'<mark style="background:{color};color:#171717">' + piece + "</mark>"
        parts.append(piece)
    return (
        '<div dir="rtl" style="white-space:pre-wrap;font:22px/1.9 serif;padding:14px">'
        + "".join(parts)
        + "</div>"
    )


def source_passage(item):
    rep = item["representative"]
    occurrence, text = rep["occurrence"], rep["record"]["text"]
    a, b = occurrence["start"], occurrence["end"]
    omissions = occurrence.get("omitted_source_tokens", [])
    ranges = []
    for omitted in omissions:
        start, end = omitted["start"], omitted["end"]
        if not a <= start < end <= b or text[start:end] != omitted["text"]:
            raise ValueError("Invalid omitted-word slice")
        ranges.append((start - a, end - a))
    return marked(text[a:b], ranges, omitted=True)


class PilotWidget:
    def __init__(self, session):
        self.session = session
        self.loading = False
        self.forms = {}
        self.header = W.HTML()
        self.input = W.HTML()
        self.pairs = W.VBox()
        self.message = W.HTML()
        self.filter = W.Dropdown(
            options=[("Pending inputs", "pending"), ("All inputs", "all")], value="pending"
        )
        self.jump = W.Dropdown(
            options=[(f"Input {i + 1} · {c['case_id']}", i) for i, c in enumerate(session.cards)]
        )
        self.filter.observe(lambda _: self.guard(self.filter_changed), "value")
        self.jump.observe(lambda _: self.guard(self.jump_changed), "value")
        self.save_next_button = W.Button(description="Save & Next", button_style="primary")
        previous = W.Button(description="Previous")
        skip = W.Button(description="Skip for now")
        save = W.Button(description="Save progress")
        for button, action in (
            (self.save_next_button, self.save_next),
            (previous, self.previous),
            (skip, self.skip),
            (save, self.save_forms),
        ):
            button.on_click(lambda _, action=action: self.guard(action))
        help_panel = W.Accordion(
            children=[
                W.HTML(
                    "<p><b>Text correspondence:</b> Yes if the input agrees with the shown source "
                    "within the allowed changes. No if it does not; "
                    "Uncertain if you cannot decide.</p>"
                    "<p><b>Boundaries:</b> Yes if both highlighted passages "
                    "start and end appropriately. "
                    "Correct lets you adjust them; Uncertain records doubt.</p>"
                    "<p>Diacritics and equivalent Arabic letter forms can differ without consuming "
                    "character edits. Pink source words were omitted from the input. "
                    "A letter insertion, "
                    "deletion or replacement uses one edit. These questions concern text only.</p>"
                    "<p>Choices and notes save automatically. "
                    "Save &amp; Next advances after all questions "
                    "on this input are answered. Uncertain is a saved, unresolved answer. "
                    "No source-occurrence or configuration-by-configuration review is needed.</p>"
                )
            ],
            selected_index=None,
        )
        help_panel.set_title(0, "Quick help")
        self.widget = W.VBox(
            [
                W.HTML(
                    "<h2>Text matching: small quality pilot</h2><p>Compare the highlighted input "
                    "with the original source passages. "
                    "No authenticity or quotation-intent judgment.</p>"
                ),
                self.header,
                self.input,
                self.pairs,
                self.save_next_button,
                self.message,
                W.HBox([previous, skip, save]),
                help_panel,
                W.HBox([self.filter, self.jump]),
            ],
            layout=W.Layout(max_width="1300px", width="100%"),
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
            self.message.value = '<p style="color:#b22">' + html.escape(str(error)) + "</p>"

    def refresh_header(self):
        completed = sum(bool(self.session.complete(c)) for c in self.session.cards)
        answers = self.session.progress["decisions"]
        answered = sum(
            bool(a[k]) for a in answers.values() for k in ("correspondence", "boundaries")
        )
        index = self.session.current
        label = (
            "Finished this view"
            if index is None
            else f"Input {index + 1} / {len(self.session.cards)}"
        )
        self.header.value = (
            f"<h3>{label}</h3><p>{completed} inputs reviewed · "
            f"{answered} / {2 * len(answers)} choices saved</p>"
        )
        if index is not None:
            group = self.session.cards[index]["group"]
            color = {
                "exact": "#215b8f",
                "fuzzy": "#6847a3",
                "natural": "#555",
                "commentary": "#176a47",
            }.get(group, "#555")
            label = html.escape(GROUP_LABELS.get(group, group))
            self.header.value += (
                f'<p style="border-left:5px solid {color};padding:10px"><b>{label}</b></p>'
            )

    def render(self):
        self.loading = True
        self.forms = {}
        try:
            self.refresh_header()
            self.message.value = ""
            if self.session.current is None:
                self.input.value = (
                    "No pending inputs. Select All inputs below to revisit saved decisions."
                )
                self.pairs.children = ()
                return
            card = self.session.cards[self.session.current]
            case = self.session.by_case[card["case_id"]]
            self.jump.value = self.session.current
            ranges = [(i["start"], i["end"]) for i in card["items"] if i["kind"] == "detection"]
            self.input.value = marked(case["text"], ranges)
            children = []
            target = case["target"]
            if target:
                expected = case["text"][target["input_start"] : target["input_end"]]
                children.append(
                    W.HTML(
                        "<p><b>Controlled positive:</b> the complete expected passage "
                        "is shown in the source comparisons below. Partial matches "
                        "are retained; they are not a complete recovery.</p>"
                        "<details><summary>Expected input passage</summary>"
                        + highlighted(expected)
                        + "</details>"
                    )
                )
            for number, item in enumerate(card["items"], 1):
                children.append(self.make_pair(case, item, number))
            if not card["items"]:
                children.append(
                    W.HTML(
                        "<p><b>No detections under any of the six settings.</b> "
                        "Nothing to compare here. Save &amp; Next acknowledges "
                        "this screen; it does not label the text quotation-free.</p>"
                    )
                )
            self.pairs.children = tuple(children)
        finally:
            self.loading = False

    def make_pair(self, case, item, number):
        rep = item["representative"]
        occurrence = rep["occurrence"]
        answer = self.session.progress["decisions"][item["item_id"]]
        config = rep["config"]
        expected = item["kind"] != "detection"
        if config:
            minimum, edits, omissions = CONFIGURATIONS[config]
            allowance = (
                f"Allows up to {edits} character edit(s) and {omissions} omitted "
                f"source word(s); minimum {minimum} input words."
            )
        else:
            allowance = (
                "Expected source construction; this complete input passage "
                "was not returned by any setting."
            )
        title = f"Passage {number}" + (" — expected, not returned" if expected else "")
        subtitle = (
            "Default settings"
            if config == DEFAULT
            else "Other settings"
            if config
            else "Known source"
        )
        description = W.HTML(
            f"<h3>{title}</h3><p><b>{subtitle}.</b> {allowance}<br>"
            f"Shown correspondence uses {occurrence['errors']} character edit(s) and "
            f"{occurrence['missing_words']} omitted word(s). "
            "Pink marks omitted source words (or symbols containing them).</p>"
            "<p>Arabic vowel marks and equivalent letter forms may differ "
            "without counting as edits.</p>"
        )
        pair = W.HBox(
            [
                W.VBox(
                    [W.HTML("<b>Matched input</b>"), W.HTML(highlighted(item["text"]))],
                    layout=W.Layout(width="50%", min_width="260px"),
                ),
                W.VBox(
                    [W.HTML("<b>Original corpus passage</b>"), W.HTML(source_passage(item))],
                    layout=W.Layout(width="50%", min_width="260px"),
                ),
            ],
            layout=W.Layout(flex_flow="row wrap"),
        )
        changed = []
        for word in occurrence.get("alignment", []):
            if word["errors"]:
                input_word = case["text"][word["input_start"] : word["input_end"]]
                source_word = rep["record"]["text"][word["source_start"] : word["source_end"]]
                changed.append(
                    '<span dir="rtl">'
                    + html.escape(input_word)
                    + " ↔ "
                    + html.escape(source_word)
                    + f"</span> ({word['errors']} edit(s))"
                )
        differences = W.HTML(
            "<p><b>Changed words:</b> " + "; ".join(changed) + "</p>" if changed else ""
        )
        correspondence = W.ToggleButtons(
            options=[("Yes", "yes"), ("No", "no"), ("Uncertain", "uncertain")],
            value=answer["correspondence"] or None,
        )
        boundaries = W.ToggleButtons(
            options=[("Yes", "yes"), ("Correct", "correct"), ("Uncertain", "uncertain")],
            value=answer["boundaries"] or None,
        )
        fields = {}
        for prefix, a, b in (
            ("input", item["start"], item["end"]),
            ("source", occurrence["start"], occurrence["end"]),
        ):
            fields[prefix + "_start"] = W.IntText(
                description=prefix.title() + " start",
                value=a if answer[prefix + "_start"] is None else answer[prefix + "_start"],
            )
            fields[prefix + "_end"] = W.IntText(
                description=prefix.title() + " end",
                value=b if answer[prefix + "_end"] is None else answer[prefix + "_end"],
            )
        preview = W.HTML()
        correction = W.VBox(
            [
                W.HTML(
                    "Change at least one boundary. Offsets count original Python characters; "
                    "the end is exclusive. The source offsets refer to the complete narration."
                ),
                W.HBox([fields["input_start"], fields["input_end"]]),
                W.HBox([fields["source_start"], fields["source_end"]]),
                preview,
            ]
        )
        correction.layout.display = "" if answer["boundaries"] == "correct" else "none"
        notes = W.Textarea(
            value=answer["notes"],
            description="Notes",
            continuous_update=False,
            layout=W.Layout(width="95%"),
        )
        note_panel = W.Accordion(children=[notes], selected_index=0 if answer["notes"] else None)
        note_panel.set_title(0, "Optional note")
        details = W.HTML(
            "<details><summary>Source, settings and original boundaries</summary>"
            "<pre style='white-space:pre-wrap'>"
            + html.escape(
                json.dumps(
                    {
                        "source": rep["record"]["hadith_key"],
                        "url": rep["record"].get("sunnah_url"),
                        "input_span": [item["start"], item["end"]],
                        "source_span": [occurrence["start"], occurrence["end"]],
                        "settings_producing_this_span": {
                            c: CONFIGURATIONS[c] for c in item["configurations"]
                        },
                        "representative_settings": config,
                        "representative_choice": rep["selection"],
                        "evidence_ids": item["evidence_ids"],
                        "alignment": occurrence.get("alignment", []),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            + "</pre></details>"
            "<details><summary>Complete original narration</summary>"
            + highlighted(rep["record"]["text"])
            + "</details>"
        )
        full_support = W.HTML()
        load_support = W.Button(
            description="Load all supporting evidence", layout=W.Layout(width="260px")
        )

        def load_complete():
            body = []
            for identity in item["evidence_ids"]:
                detection = self.session.evidence(identity)
                body.append(
                    "<details><summary>"
                    + html.escape(identity)
                    + f" · {len(detection['references'])} references</summary>"
                    + "<pre style='white-space:pre-wrap'>"
                    + html.escape(json.dumps(detection, ensure_ascii=False, indent=2))
                    + "</pre></details>"
                )
            full_support.value = "".join(body) or "This is a frozen target, not detector output."

        load_support.on_click(lambda _: self.guard(load_complete))
        advanced = W.Accordion(
            children=[
                W.VBox(
                    [
                        details,
                        W.HTML(
                            "All original reference records, occurrences and traces are retained. "
                            "Loading them is optional and may display a large amount of evidence."
                        ),
                        load_support,
                        full_support,
                    ]
                )
            ],
            selected_index=None,
        )
        advanced.set_title(0, "Advanced evidence (optional)")
        form = {
            "correspondence": correspondence,
            "boundaries": boundaries,
            "fields": fields,
            "notes": notes,
            "correction": correction,
            "preview": preview,
            "item": item,
            "case": case,
        }
        self.forms[item["item_id"]] = form
        for control in (correspondence, boundaries, notes, *fields.values()):
            control.observe(
                lambda _, identity=item["item_id"]: self.guard(lambda: self.autosave(identity)),
                "value",
            )
        return W.VBox(
            [
                description,
                pair,
                differences,
                W.HTML("<b>Do these passages correspond textually within the allowed changes?</b>"),
                correspondence,
                W.HTML("<b>Are the input and source boundaries appropriate?</b>"),
                boundaries,
                correction,
                note_panel,
                advanced,
            ],
            layout=W.Layout(border="1px solid #bbb", padding="16px", margin="10px 0"),
        )

    def values(self, form):
        output = {
            "correspondence": form["correspondence"].value or "",
            "boundaries": form["boundaries"].value or "",
            "notes": form["notes"].value,
            "input_start": None,
            "input_end": None,
            "source_start": None,
            "source_end": None,
        }
        form["correction"].layout.display = "" if output["boundaries"] == "correct" else "none"
        form["preview"].value = ""
        if output["boundaries"] == "correct":
            item = form["item"]
            occurrence = item["representative"]["occurrence"]
            for prefix, text, a, b in (
                ("input", form["case"]["text"], item["start"], item["end"]),
                (
                    "source",
                    item["representative"]["record"]["text"],
                    occurrence["start"],
                    occurrence["end"],
                ),
            ):
                start, end = (
                    form["fields"][prefix + "_start"].value,
                    form["fields"][prefix + "_end"].value,
                )
                if (start, end) != (a, b):
                    output[prefix + "_start"], output[prefix + "_end"] = start, end
                form["preview"].value += f"<b>{prefix.title()} preview</b>" + highlighted(
                    text, start, end
                )
        return output

    def autosave(self, identity):
        self.session.update(identity, **self.values(self.forms[identity]))
        self.refresh_header()
        self.message.value = "Saved automatically."

    def save_forms(self):
        proposed = copy.deepcopy(self.session.progress)
        for identity, form in self.forms.items():
            proposed["decisions"][identity] = self.values(form)
        self.session.save(proposed)
        self.refresh_header()
        self.message.value = "Progress saved."

    def save_next(self):
        self.save_forms()
        if self.session.current is None:
            return
        card = self.session.cards[self.session.current]
        if not card["items"]:
            self.session.acknowledge(card["case_id"])
        if not self.session.complete(card):
            raise ValueError(
                "Answer both questions for each passage, and finish boundary corrections; "
                "or use Skip for now."
            )
        self.advance(1)

    def advance(self, step):
        start = self.session.current if self.session.current is not None else -1
        order = [
            (start + step * n) % len(self.session.cards)
            for n in range(1, len(self.session.cards) + 1)
        ]
        self.session.current = next(
            (
                n
                for n in order
                if self.filter.value == "all" or not self.session.complete(self.session.cards[n])
            ),
            None,
        )
        self.render()

    def previous(self):
        self.save_forms()
        self.loading = True
        self.filter.value = "all"
        self.loading = False
        self.advance(-1)

    def skip(self):
        self.save_forms()
        self.advance(1)

    def filter_changed(self):
        self.save_forms()
        self.session.current = next(
            (
                n
                for n, c in enumerate(self.session.cards)
                if self.filter.value == "all" or not self.session.complete(c)
            ),
            None,
        )
        self.render()

    def jump_changed(self):
        self.save_forms()
        self.session.current = self.jump.value
        self.render()


def create_pilot_ui(session):
    return PilotWidget(session)
