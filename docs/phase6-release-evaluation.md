# Evaluation wording for a future README / PyPI description

Prepared wording only; this does not publish a release.

## README-sized text

A frozen 55-input technical pilot contained 10 exact excerpts, 10 controlled modified excerpts (4 character-edit, 4 omission, 2 combined), 15 general Arabic paragraphs and 20 religious-commentary paragraphs. A maintainer accepted textual correspondence and boundaries for 191/191 displayed input/source pairs, completing 382 judgments. The default `(5,0,0)` recovered 10/10 exact targets; `(5,1,1)` recovered 4/4 edit, 4/4 omission and 2/2 combined targets. The default's zero fuzzy budgets did not fully recover those 10 controlled modified targets. There were 0/15 general-prose paragraphs with default detections, and 58 default detections across 20/20 commentary paragraphs. Commentary detections are textual matches, not independently labelled intended quotations or false positives. These small, reused samples do not establish deployment-wide precision/recall or Hadith authenticity.

## Short PyPI-sized text

In a frozen 55-input technical pilot, a maintainer accepted textual correspondence and boundaries for 191/191 displayed source pairs. Defaults recovered 10/10 exact targets; enabling one character edit and one source-word omission recovered 10/10 controlled modified targets. This limited pilot does not measure deployment-wide precision/recall, intended quotation or Hadith authenticity.
