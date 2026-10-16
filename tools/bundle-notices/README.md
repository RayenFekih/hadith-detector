---
license: other
license_name: mixed-per-row-pd-arabic-and-reference
pretty_name: "QuranLab — Hadith & Sunnah (Ahl al-Sunnah)"
language:
  - ar
task_categories:
  - text-retrieval
  - text-classification
  - text-generation
  - question-answering
annotations_creators:
  - expert-generated
language_creators:
  - expert-generated
  - found
multilinguality:
  - multilingual
source_datasets:
  - original
size_categories:
  - 100K<n<1M
tags:
  - hadith
  - sunnah
  - islam
  - arabic
  - ahl-al-sunnah
  - bukhari
  - muslim
  - kutub-al-sittah
  - hadith-grading
  - isnad
  - religious-text
  - multilingual
  - text
  - datasets
  - pandas
  - dask
  - mlcroissant
configs:
  - config_name: index
    default: true
    data_files:
      - split: train
        path: "index/train-00000-of-00001.parquet"
  - config_name: collections
    data_files:
      - split: train
        path: "collections/train-00000-of-00001.parquet"
  - config_name: abudawud-ar
    data_files:
      - split: train
        path: "abudawud-ar/train-00000-of-00001.parquet"
  - config_name: abudawud-bn
    data_files:
      - split: train
        path: "abudawud-bn/train-00000-of-00001.parquet"
  - config_name: abudawud-en
    data_files:
      - split: train
        path: "abudawud-en/train-00000-of-00001.parquet"
  - config_name: abudawud-fr
    data_files:
      - split: train
        path: "abudawud-fr/train-00000-of-00001.parquet"
  - config_name: abudawud-id
    data_files:
      - split: train
        path: "abudawud-id/train-00000-of-00001.parquet"
  - config_name: abudawud-ru
    data_files:
      - split: train
        path: "abudawud-ru/train-00000-of-00001.parquet"
  - config_name: abudawud-tr
    data_files:
      - split: train
        path: "abudawud-tr/train-00000-of-00001.parquet"
  - config_name: abudawud-ur
    data_files:
      - split: train
        path: "abudawud-ur/train-00000-of-00001.parquet"
  - config_name: ahmad-ar
    data_files:
      - split: train
        path: "ahmad-ar/train-00000-of-00001.parquet"
  - config_name: bukhari-ar
    data_files:
      - split: train
        path: "bukhari-ar/train-00000-of-00001.parquet"
  - config_name: bukhari-bn
    data_files:
      - split: train
        path: "bukhari-bn/train-00000-of-00001.parquet"
  - config_name: bukhari-en
    data_files:
      - split: train
        path: "bukhari-en/train-00000-of-00001.parquet"
  - config_name: bukhari-fr
    data_files:
      - split: train
        path: "bukhari-fr/train-00000-of-00001.parquet"
  - config_name: bukhari-id
    data_files:
      - split: train
        path: "bukhari-id/train-00000-of-00001.parquet"
  - config_name: bukhari-ru
    data_files:
      - split: train
        path: "bukhari-ru/train-00000-of-00001.parquet"
  - config_name: bukhari-ta
    data_files:
      - split: train
        path: "bukhari-ta/train-00000-of-00001.parquet"
  - config_name: bukhari-tr
    data_files:
      - split: train
        path: "bukhari-tr/train-00000-of-00001.parquet"
  - config_name: bukhari-ur
    data_files:
      - split: train
        path: "bukhari-ur/train-00000-of-00001.parquet"
  - config_name: darimi-ar
    data_files:
      - split: train
        path: "darimi-ar/train-00000-of-00001.parquet"
  - config_name: dehlawi-ar
    data_files:
      - split: train
        path: "dehlawi-ar/train-00000-of-00001.parquet"
  - config_name: dehlawi-en
    data_files:
      - split: train
        path: "dehlawi-en/train-00000-of-00001.parquet"
  - config_name: dehlawi-fr
    data_files:
      - split: train
        path: "dehlawi-fr/train-00000-of-00001.parquet"
  - config_name: hadeethenc-ak
    data_files:
      - split: train
        path: "hadeethenc-ak/train-00000-of-00001.parquet"
  - config_name: hadeethenc-am
    data_files:
      - split: train
        path: "hadeethenc-am/train-00000-of-00001.parquet"
  - config_name: hadeethenc-ar
    data_files:
      - split: train
        path: "hadeethenc-ar/train-00000-of-00001.parquet"
  - config_name: hadeethenc-as
    data_files:
      - split: train
        path: "hadeethenc-as/train-00000-of-00001.parquet"
  - config_name: hadeethenc-az
    data_files:
      - split: train
        path: "hadeethenc-az/train-00000-of-00001.parquet"
  - config_name: hadeethenc-bg
    data_files:
      - split: train
        path: "hadeethenc-bg/train-00000-of-00001.parquet"
  - config_name: hadeethenc-bm
    data_files:
      - split: train
        path: "hadeethenc-bm/train-00000-of-00001.parquet"
  - config_name: hadeethenc-bn
    data_files:
      - split: train
        path: "hadeethenc-bn/train-00000-of-00001.parquet"
  - config_name: hadeethenc-bs
    data_files:
      - split: train
        path: "hadeethenc-bs/train-00000-of-00001.parquet"
  - config_name: hadeethenc-cs
    data_files:
      - split: train
        path: "hadeethenc-cs/train-00000-of-00001.parquet"
  - config_name: hadeethenc-da
    data_files:
      - split: train
        path: "hadeethenc-da/train-00000-of-00001.parquet"
  - config_name: hadeethenc-de
    data_files:
      - split: train
        path: "hadeethenc-de/train-00000-of-00001.parquet"
  - config_name: hadeethenc-el
    data_files:
      - split: train
        path: "hadeethenc-el/train-00000-of-00001.parquet"
  - config_name: hadeethenc-en
    data_files:
      - split: train
        path: "hadeethenc-en/train-00000-of-00001.parquet"
  - config_name: hadeethenc-es
    data_files:
      - split: train
        path: "hadeethenc-es/train-00000-of-00001.parquet"
  - config_name: hadeethenc-fa
    data_files:
      - split: train
        path: "hadeethenc-fa/train-00000-of-00001.parquet"
  - config_name: hadeethenc-ff
    data_files:
      - split: train
        path: "hadeethenc-ff/train-00000-of-00001.parquet"
  - config_name: hadeethenc-fr
    data_files:
      - split: train
        path: "hadeethenc-fr/train-00000-of-00001.parquet"
  - config_name: hadeethenc-gu
    data_files:
      - split: train
        path: "hadeethenc-gu/train-00000-of-00001.parquet"
  - config_name: hadeethenc-ha
    data_files:
      - split: train
        path: "hadeethenc-ha/train-00000-of-00001.parquet"
  - config_name: hadeethenc-hi
    data_files:
      - split: train
        path: "hadeethenc-hi/train-00000-of-00001.parquet"
  - config_name: hadeethenc-hu
    data_files:
      - split: train
        path: "hadeethenc-hu/train-00000-of-00001.parquet"
  - config_name: hadeethenc-id
    data_files:
      - split: train
        path: "hadeethenc-id/train-00000-of-00001.parquet"
  - config_name: hadeethenc-it
    data_files:
      - split: train
        path: "hadeethenc-it/train-00000-of-00001.parquet"
  - config_name: hadeethenc-ja
    data_files:
      - split: train
        path: "hadeethenc-ja/train-00000-of-00001.parquet"
  - config_name: hadeethenc-ka
    data_files:
      - split: train
        path: "hadeethenc-ka/train-00000-of-00001.parquet"
  - config_name: hadeethenc-km
    data_files:
      - split: train
        path: "hadeethenc-km/train-00000-of-00001.parquet"
  - config_name: hadeethenc-kmr
    data_files:
      - split: train
        path: "hadeethenc-kmr/train-00000-of-00001.parquet"
  - config_name: hadeethenc-kn
    data_files:
      - split: train
        path: "hadeethenc-kn/train-00000-of-00001.parquet"
  - config_name: hadeethenc-ku
    data_files:
      - split: train
        path: "hadeethenc-ku/train-00000-of-00001.parquet"
  - config_name: hadeethenc-ky
    data_files:
      - split: train
        path: "hadeethenc-ky/train-00000-of-00001.parquet"
  - config_name: hadeethenc-ln
    data_files:
      - split: train
        path: "hadeethenc-ln/train-00000-of-00001.parquet"
  - config_name: hadeethenc-lt
    data_files:
      - split: train
        path: "hadeethenc-lt/train-00000-of-00001.parquet"
  - config_name: hadeethenc-mg
    data_files:
      - split: train
        path: "hadeethenc-mg/train-00000-of-00001.parquet"
  - config_name: hadeethenc-mk
    data_files:
      - split: train
        path: "hadeethenc-mk/train-00000-of-00001.parquet"
  - config_name: hadeethenc-ml
    data_files:
      - split: train
        path: "hadeethenc-ml/train-00000-of-00001.parquet"
  - config_name: hadeethenc-mos
    data_files:
      - split: train
        path: "hadeethenc-mos/train-00000-of-00001.parquet"
  - config_name: hadeethenc-mr
    data_files:
      - split: train
        path: "hadeethenc-mr/train-00000-of-00001.parquet"
  - config_name: hadeethenc-ms
    data_files:
      - split: train
        path: "hadeethenc-ms/train-00000-of-00001.parquet"
  - config_name: hadeethenc-my
    data_files:
      - split: train
        path: "hadeethenc-my/train-00000-of-00001.parquet"
  - config_name: hadeethenc-ne
    data_files:
      - split: train
        path: "hadeethenc-ne/train-00000-of-00001.parquet"
  - config_name: hadeethenc-nl
    data_files:
      - split: train
        path: "hadeethenc-nl/train-00000-of-00001.parquet"
  - config_name: hadeethenc-om
    data_files:
      - split: train
        path: "hadeethenc-om/train-00000-of-00001.parquet"
  - config_name: hadeethenc-pa
    data_files:
      - split: train
        path: "hadeethenc-pa/train-00000-of-00001.parquet"
  - config_name: hadeethenc-prs
    data_files:
      - split: train
        path: "hadeethenc-prs/train-00000-of-00001.parquet"
  - config_name: hadeethenc-ps
    data_files:
      - split: train
        path: "hadeethenc-ps/train-00000-of-00001.parquet"
  - config_name: hadeethenc-pt
    data_files:
      - split: train
        path: "hadeethenc-pt/train-00000-of-00001.parquet"
  - config_name: hadeethenc-rn
    data_files:
      - split: train
        path: "hadeethenc-rn/train-00000-of-00001.parquet"
  - config_name: hadeethenc-ro
    data_files:
      - split: train
        path: "hadeethenc-ro/train-00000-of-00001.parquet"
  - config_name: hadeethenc-ru
    data_files:
      - split: train
        path: "hadeethenc-ru/train-00000-of-00001.parquet"
  - config_name: hadeethenc-rw
    data_files:
      - split: train
        path: "hadeethenc-rw/train-00000-of-00001.parquet"
  - config_name: hadeethenc-si
    data_files:
      - split: train
        path: "hadeethenc-si/train-00000-of-00001.parquet"
  - config_name: hadeethenc-so
    data_files:
      - split: train
        path: "hadeethenc-so/train-00000-of-00001.parquet"
  - config_name: hadeethenc-sq
    data_files:
      - split: train
        path: "hadeethenc-sq/train-00000-of-00001.parquet"
  - config_name: hadeethenc-sr
    data_files:
      - split: train
        path: "hadeethenc-sr/train-00000-of-00001.parquet"
  - config_name: hadeethenc-sv
    data_files:
      - split: train
        path: "hadeethenc-sv/train-00000-of-00001.parquet"
  - config_name: hadeethenc-sw
    data_files:
      - split: train
        path: "hadeethenc-sw/train-00000-of-00001.parquet"
  - config_name: hadeethenc-ta
    data_files:
      - split: train
        path: "hadeethenc-ta/train-00000-of-00001.parquet"
  - config_name: hadeethenc-te
    data_files:
      - split: train
        path: "hadeethenc-te/train-00000-of-00001.parquet"
  - config_name: hadeethenc-tg
    data_files:
      - split: train
        path: "hadeethenc-tg/train-00000-of-00001.parquet"
  - config_name: hadeethenc-th
    data_files:
      - split: train
        path: "hadeethenc-th/train-00000-of-00001.parquet"
  - config_name: hadeethenc-tl
    data_files:
      - split: train
        path: "hadeethenc-tl/train-00000-of-00001.parquet"
  - config_name: hadeethenc-tr
    data_files:
      - split: train
        path: "hadeethenc-tr/train-00000-of-00001.parquet"
  - config_name: hadeethenc-ug
    data_files:
      - split: train
        path: "hadeethenc-ug/train-00000-of-00001.parquet"
  - config_name: hadeethenc-uk
    data_files:
      - split: train
        path: "hadeethenc-uk/train-00000-of-00001.parquet"
  - config_name: hadeethenc-ur
    data_files:
      - split: train
        path: "hadeethenc-ur/train-00000-of-00001.parquet"
  - config_name: hadeethenc-uz
    data_files:
      - split: train
        path: "hadeethenc-uz/train-00000-of-00001.parquet"
  - config_name: hadeethenc-vi
    data_files:
      - split: train
        path: "hadeethenc-vi/train-00000-of-00001.parquet"
  - config_name: hadeethenc-wo
    data_files:
      - split: train
        path: "hadeethenc-wo/train-00000-of-00001.parquet"
  - config_name: hadeethenc-yao
    data_files:
      - split: train
        path: "hadeethenc-yao/train-00000-of-00001.parquet"
  - config_name: hadeethenc-yo
    data_files:
      - split: train
        path: "hadeethenc-yo/train-00000-of-00001.parquet"
  - config_name: hadeethenc-zh
    data_files:
      - split: train
        path: "hadeethenc-zh/train-00000-of-00001.parquet"
  - config_name: ibnmajah-ar
    data_files:
      - split: train
        path: "ibnmajah-ar/train-00000-of-00001.parquet"
  - config_name: ibnmajah-bn
    data_files:
      - split: train
        path: "ibnmajah-bn/train-00000-of-00001.parquet"
  - config_name: ibnmajah-en
    data_files:
      - split: train
        path: "ibnmajah-en/train-00000-of-00001.parquet"
  - config_name: ibnmajah-fr
    data_files:
      - split: train
        path: "ibnmajah-fr/train-00000-of-00001.parquet"
  - config_name: ibnmajah-id
    data_files:
      - split: train
        path: "ibnmajah-id/train-00000-of-00001.parquet"
  - config_name: ibnmajah-tr
    data_files:
      - split: train
        path: "ibnmajah-tr/train-00000-of-00001.parquet"
  - config_name: ibnmajah-ur
    data_files:
      - split: train
        path: "ibnmajah-ur/train-00000-of-00001.parquet"
  - config_name: malik-ar
    data_files:
      - split: train
        path: "malik-ar/train-00000-of-00001.parquet"
  - config_name: malik-bn
    data_files:
      - split: train
        path: "malik-bn/train-00000-of-00001.parquet"
  - config_name: malik-en
    data_files:
      - split: train
        path: "malik-en/train-00000-of-00001.parquet"
  - config_name: malik-fr
    data_files:
      - split: train
        path: "malik-fr/train-00000-of-00001.parquet"
  - config_name: malik-id
    data_files:
      - split: train
        path: "malik-id/train-00000-of-00001.parquet"
  - config_name: malik-tr
    data_files:
      - split: train
        path: "malik-tr/train-00000-of-00001.parquet"
  - config_name: malik-ur
    data_files:
      - split: train
        path: "malik-ur/train-00000-of-00001.parquet"
  - config_name: muslim-ar
    data_files:
      - split: train
        path: "muslim-ar/train-00000-of-00001.parquet"
  - config_name: muslim-bn
    data_files:
      - split: train
        path: "muslim-bn/train-00000-of-00001.parquet"
  - config_name: muslim-en
    data_files:
      - split: train
        path: "muslim-en/train-00000-of-00001.parquet"
  - config_name: muslim-fr
    data_files:
      - split: train
        path: "muslim-fr/train-00000-of-00001.parquet"
  - config_name: muslim-id
    data_files:
      - split: train
        path: "muslim-id/train-00000-of-00001.parquet"
  - config_name: muslim-ru
    data_files:
      - split: train
        path: "muslim-ru/train-00000-of-00001.parquet"
  - config_name: muslim-ta
    data_files:
      - split: train
        path: "muslim-ta/train-00000-of-00001.parquet"
  - config_name: muslim-tr
    data_files:
      - split: train
        path: "muslim-tr/train-00000-of-00001.parquet"
  - config_name: muslim-ur
    data_files:
      - split: train
        path: "muslim-ur/train-00000-of-00001.parquet"
  - config_name: nasai-ar
    data_files:
      - split: train
        path: "nasai-ar/train-00000-of-00001.parquet"
  - config_name: nasai-bn
    data_files:
      - split: train
        path: "nasai-bn/train-00000-of-00001.parquet"
  - config_name: nasai-en
    data_files:
      - split: train
        path: "nasai-en/train-00000-of-00001.parquet"
  - config_name: nasai-fr
    data_files:
      - split: train
        path: "nasai-fr/train-00000-of-00001.parquet"
  - config_name: nasai-id
    data_files:
      - split: train
        path: "nasai-id/train-00000-of-00001.parquet"
  - config_name: nasai-tr
    data_files:
      - split: train
        path: "nasai-tr/train-00000-of-00001.parquet"
  - config_name: nasai-ur
    data_files:
      - split: train
        path: "nasai-ur/train-00000-of-00001.parquet"
  - config_name: nawawi-ar
    data_files:
      - split: train
        path: "nawawi-ar/train-00000-of-00001.parquet"
  - config_name: nawawi-bn
    data_files:
      - split: train
        path: "nawawi-bn/train-00000-of-00001.parquet"
  - config_name: nawawi-en
    data_files:
      - split: train
        path: "nawawi-en/train-00000-of-00001.parquet"
  - config_name: nawawi-fr
    data_files:
      - split: train
        path: "nawawi-fr/train-00000-of-00001.parquet"
  - config_name: nawawi-tr
    data_files:
      - split: train
        path: "nawawi-tr/train-00000-of-00001.parquet"
  - config_name: qudsi-ar
    data_files:
      - split: train
        path: "qudsi-ar/train-00000-of-00001.parquet"
  - config_name: qudsi-en
    data_files:
      - split: train
        path: "qudsi-en/train-00000-of-00001.parquet"
  - config_name: qudsi-fr
    data_files:
      - split: train
        path: "qudsi-fr/train-00000-of-00001.parquet"
  - config_name: tirmidhi-ar
    data_files:
      - split: train
        path: "tirmidhi-ar/train-00000-of-00001.parquet"
  - config_name: tirmidhi-bn
    data_files:
      - split: train
        path: "tirmidhi-bn/train-00000-of-00001.parquet"
  - config_name: tirmidhi-en
    data_files:
      - split: train
        path: "tirmidhi-en/train-00000-of-00001.parquet"
  - config_name: tirmidhi-id
    data_files:
      - split: train
        path: "tirmidhi-id/train-00000-of-00001.parquet"
  - config_name: tirmidhi-tr
    data_files:
      - split: train
        path: "tirmidhi-tr/train-00000-of-00001.parquet"
  - config_name: tirmidhi-ur
    data_files:
      - split: train
        path: "tirmidhi-ur/train-00000-of-00001.parquet"
---

# Dataset Card for QuranLab — Hadith &amp; Sunnah (Ahl al-Sunnah)

![Theology: Ahl al-Sunnah](https://img.shields.io/badge/theology-Ahl%20al--Sunnah-2ea44f) ![Arabic matn: public domain](https://img.shields.io/badge/Arabic%20matn-public%20domain-4c6ef5) ![Collections: 13](https://img.shields.io/badge/collections-13-orange) ![Hadith: 65K+](https://img.shields.io/badge/hadith-65K%2B-blue) ![Languages: 72](https://img.shields.io/badge/languages-72-9cf)

A clean **Ahl-al-Sunnah hadith corpus**: the canonical Sunni collections (the Six Books + the
Muwaṭṭaʾ, Musnad Aḥmad, al-Dārimī, and the famous forty-collections) in **Arabic plus many
translations**, with **grader-attributed gradings** — one **config per
(collection × language)**. This is the audio/text family's hadith modality — companion to
[**`quranlab/quran`**](https://huggingface.co/datasets/quranlab/quran) (Qurʾan text) and
[**`quranlab/quran-audio`**](https://huggingface.co/datasets/quranlab/quran-audio) (recitation).

**QuranLab is a volunteer, non-commercial, community-service project.** This dataset is offered
freely to students, researchers, and developers building tools for studying the Sunnah of the
Prophet ﷺ. It is strictly **Ahl al-Sunnah wa'l-Jamāʿah**: sources outside Sunni orthodoxy (the
Shia canon, Ibāḍī, Ahmadiyya, hadith-rejecter framings) are excluded by design.

---

QuranLab is a volunteer effort. Our aim is to present these works carefully and at high quality, and to help them travel faithfully — in the spirit in which they were written — not to claim them as ours.

The text here reaches you through the work of fawazahmed0/hadith-api, mhashim6/Open-Hadith-Data and HadeethEnc.com. Who to thank, and what we consulted without ever quoting, is set out in [`SOURCES.md`](SOURCES.md).

## What's inside

**13 collections — Arabic + translations + grades.** The Six Books, the Muwaṭṭaʾ and the
famous forty-collections come aligned across languages with multi-grader gradings; **Musnad Aḥmad
and al-Dārimī** are Arabic *matn*; and a many-language graded selection covers HadeethEnc's
material. Each collection below is the work of the muḥaddith who compiled it — the repositories we
drew the text from are listed in `LICENSES.md`.

| collection | name | author | type | hadith | languages | graded |
|---|---|---|---|---|---|---|
| `ahmad` | Musnad Ahmad (مسند أحمد) | Ahmad ibn Hanbal, d. 241 AH | musnad | 26,363 | 1 | — |
| `darimi` | Sunan al-Darimi (سنن الدارمي) | Abd Allah ibn Abd al-Rahman al-Darimi, d. 255 AH | sunan | 3,367 | 1 | — |
| `bukhari` | Sahih al-Bukhari (صحيح البخاري) | Muhammad ibn Ismail al-Bukhari, d. 256 AH | sahih | 7,580 | 9 | — |
| `muslim` | Sahih Muslim (صحيح مسلم) | Muslim ibn al-Hajjaj al-Naysaburi, d. 261 AH | sahih | 7,360 | 9 | — |
| `abudawud` | Sunan Abi Dawud (سنن أبي داود) | Abu Dawud al-Sijistani, d. 275 AH | sunan | 5,272 | 8 | ✅ |
| `tirmidhi` | Jami' al-Tirmidhi (جامع الترمذي) | Muhammad ibn Isa al-Tirmidhi, d. 279 AH | jami | 3,924 | 6 | ✅ |
| `nasai` | Sunan an-Nasa'i (al-Mujtaba) (سنن النسائي (المجتبى)) | Ahmad ibn Shu'ayb al-Nasa'i, d. 303 AH | sunan | 5,679 | 7 | ✅ |
| `ibnmajah` | Sunan Ibn Majah (سنن ابن ماجه) | Muhammad ibn Yazid Ibn Majah, d. 273 AH | sunan | 4,338 | 7 | ✅ |
| `malik` | Muwatta Malik (موطأ مالك) | Malik ibn Anas, d. 179 AH | muwatta | 1,829 | 7 | ✅ |
| `nawawi` | Forty Hadith of al-Nawawi (الأربعون النووية) | Yahya ibn Sharaf al-Nawawi, d. 676 AH | forty | 42 | 5 | — |
| `qudsi` | Forty Hadith Qudsi (الأربعون القدسية) | (compilation) | forty-qudsi | 40 | 3 | — |
| `dehlawi` | Forty Hadith of Shah Wali Allah al-Dihlawi (الأربعون للشاه ولي الله الدهلوي) | Shah Wali Allah al-Dihlawi, d. 1176 AH | forty | 40 | 3 | — |
| `hadeethenc` | HadeethEnc — graded multilingual selection (موسوعة الأحاديث النبوية المترجمة) | IslamHouse / Saudi Ministry of Islamic Affairs | graded-selection | 3,574 | 72 | ✅ |

> **On grading.** Gradings are **grader-attributed, never asserted by us**, and never auto-stamped.
> The four Sunan, the Muwaṭṭaʾ and the forty-collections (from fawazahmed0) carry per-hadith gradings
> from multiple muḥaddiths (al-Albānī, Aḥmad Shākir, Zubair ʿAlī Zaʾī, …) in the `grades` column;
> every HadeethEnc row carries a grade + attribution. The two Ṣaḥīḥs are ṣaḥīḥ by Sunni consensus (a
> *collection-level* note in the `collections` config). The Arabic *matn* of Musnad Aḥmad and
> al-Dārimī (mhashim6) is left **ungraded** — we don't hold per-hadith grades for it, so we assert none.


## Graded multilingual layer — HadeethEnc (72 languages)

In addition to the Arabic Nine Books, this dataset includes **3,574 curated, authentic prophetic
hadith in 72 languages** from [HadeethEnc.com](https://hadeethenc.com) (the Encyclopedia of
Translated Prophetic Hadiths — a service of IslamHouse / the Saudi Ministry of Islamic Affairs), one
config per language (`hadeethenc-<lang>`). Unlike the Arabic matn spine, **every HadeethEnc hadith
carries a grade and an attribution** (e.g. *Authentic*, *Agreed upon*), reproduced **verbatim** with
its version. Each row: `hadith_key, hadeethenc_id, language, title, text, intro, grade,
grader, grade_source, attribution_text, explanation, status, theological_status, source, license,
attribution`.

---

## Quick start

```python
from datasets import load_dataset

# Default: a slim cross-collection index of every hadith
index = load_dataset("quranlab/hadith")

# One collection — Arabic, and an aligned translation (join on hadith_number)
bukhari_ar = load_dataset("quranlab/hadith", "bukhari-ar", split="train")
bukhari_en = load_dataset("quranlab/hadith", "bukhari-en", split="train")

# A graded Sunan — the `grades` column carries multiple muhaddith verdicts
tirmidhi = load_dataset("quranlab/hadith", "tirmidhi-en", split="train")

# The collection registry (authors, types, counts, languages, status notes)
collections = load_dataset("quranlab/hadith", "collections", split="train")
# Graded, multilingual selection (HadeethEnc) — e.g. English / Turkish
he_en = load_dataset("quranlab/hadith", "hadeethenc-en", split="train")
he_tr = load_dataset("quranlab/hadith", "hadeethenc-tr", split="train")
```

Within a fawazahmed0-sourced collection, the Arabic and each translation **align by `hadith_number`**
(the standard Abdul-Baqi / sunnah.com numbering). The primary keys are `hadith_key`
(`"{collection}:{number}"`, citable) and `urn` (a stable unique integer per row).

---

## Structure & fields

- **`index`** *(default)* — slim cross-collection spine (one row per hadith, Arabic): `hadith_key,
  urn, seq, collection, collection_type, hadith_number, language, n_languages, n_chars, has_grade,
  has_text`.
- **`collections`** — one row per collection: id, names (ar/en), author, death year (AH), type,
  school, hadith count, `languages`, `n_languages`, `graded`, `numbering`, `source`, `status_note`.
- **`{collection}-{lang}`** — one config per (collection × language). fawazahmed0 collections
  carry: `hadith_key, urn, seq, collection, language, hadith_number, number_sort, book_number,
  in_book_number, sunnah_url, text, grades` (a list of `{grader, grade}`), `n_grades,
  grade_summary, is_muallaq`. mhashim6 Arabic (`ahmad-ar`, `darimi-ar`) is matn-only (ungraded).
  HadeethEnc (`hadeethenc-{lang}`) adds `title, intro, grade, grader, grade_source,
  attribution_text, explanation`.
- **`metadata/configs.csv`** — one row per config with its collection names, numbering, terms and
  credit. These describe the config, not the individual hadith, so they are not repeated on
  every row.

`hadith_number` is a **string** (numbering follows the source edition); `urn` is the unique row id;
`seq` is a contiguous 1..N spine within each edition.

---

## Scope, sources & licensing

- **Theology:** strictly **Ahl al-Sunnah**. Excluded by design (see the project's governance):
  the Shia Four Books and other Shia/Ismāʿīlī collections, Ibāḍī (Musnad al-Rabīʿ), Ahmadiyya,
  Quranist/hadith-rejecter sources, and hostile-orientalist grade framings.
- **Arabic matn:** public domain, kept verbatim.
- **Translations and gradings:** the work of their translators, publishers, and the muḥaddith
  graders, included with full credit.
- **Graded multilingual selection:** verbatim, version-pinned hadith from HadeethEnc, each with its
  grade and attribution.
- **Diyanet (Turkish official):** *Hadislerle İslam* — the DİB's thematic exposition of the Sunnah
  (Kütüb-i Tis'a only), page-grain Turkish with cited Arabic matn and canonical cross-references.
- **Reference links:** fawazahmed0-sourced hadith carry a `sunnah_url` to the matching page on
  [sunnah.com](https://sunnah.com) — a link only.
- **Roadmap:** more Tier-2/3 collections, a per-hadith cross-collection `xref` graph, and a `rijāl`
  (narrator) layer.

Per-collection credits and terms are in `LICENSES.md` and `metadata/`. If you hold rights to a work
here and would like it removed, open a discussion on the **Community** tab; we act promptly.

---

## The QuranLab family

These datasets are built by the same volunteers and are meant to be used together; they join on
shared keys — `verse_key` on the Qur'an side, `hadith_key` on the Sunnah side.

| Dataset | What it holds |
|---|---|
| [`quranlab/quran`](https://huggingface.co/datasets/quranlab/quran) | Qur'an text, multilingual translations, tafsir, word-level morphology |
| [`quranlab/quran-audio`](https://huggingface.co/datasets/quranlab/quran-audio) | Recitation reference manifest and CC-BY word timing (references only, no audio files) |
| [`quranlab/hadith`](https://huggingface.co/datasets/quranlab/hadith) | Nine Books Arabic matn, translations, and normalized authenticity grades |
| [`quranlab/islamic-corpus-graph`](https://huggingface.co/datasets/quranlab/islamic-corpus-graph) | The above linked into one structured graph, with retrieval passages and a held-out evaluation set |

You are reading the card for **`quranlab/hadith`**. Corrections, additions, and removal requests are
welcome on any of them through the **Community** tab.

---

## Acknowledgments

With gratitude to [`mhashim6/Open-Hadith-Data`](https://github.com/mhashim6/Open-Hadith-Data) for
the open Arabic matn, and to the scholars and institutions who have preserved and transmitted the
Sunnah across the centuries. Above all, this is offered seeking the pleasure of Allah.

## Citation

```bibtex
@misc{quranlab_hadith_2026,
  title        = {QuranLab --- Hadith (Ahl al-Sunnah): the Nine Books},
  author       = {{QuranLab}},
  year         = {2026},
  publisher    = {Hugging Face},
  howpublished = {\url{https://huggingface.co/datasets/quranlab/hadith}}
}
```

> *Offered freely as a service to the worldwide community of learners — that the Sunnah of the
> Prophet ﷺ be a little easier to study, build with, and share. May it be of benefit.*

## For agents and pipelines

Deterministic facts an automated consumer needs, so nothing has to be inferred
from a sample.

- **Config naming:** `{collection}-{lang}` — e.g. `bukhari-ar`, `bukhari-en`; plus `index` (cross-collection spine) and `collections` (registry)
- **Join key:** `hadith_key` (`collection:number`) across languages; `urn` is the unique row id
- **Default config:** `index`
- **Format:** Parquet, one directory per config, split `train`.
- **Terms and credit** are per config in `metadata/`, never per row — join on the
  config name when you need them.
- **Never infer a grade.** `grade` / `grades` are populated only where a named muhaddith graded that hadith; an empty grade means no grade is known, not “unauthenticated”.
- `attribution_text` is the hadith's own chain/companion attribution — content, not a licence field.
- Start from `index` to discover what exists, then load the specific `{collection}-{lang}` config.

Inspect it without downloading the data:

```bash
# every config and split
curl https://datasets-server.huggingface.co/splits?dataset=quranlab/hadith

# a first page of rows
curl "https://datasets-server.huggingface.co/first-rows?dataset=quranlab/hadith&config=bukhari-ar&split=train"

# machine-readable schema and provenance (Croissant JSON-LD)
curl https://huggingface.co/api/datasets/quranlab/hadith/croissant
```

Query it in place with SQL — no full download:

```bash
hf datasets sql quranlab/hadith "SELECT * FROM 'bukhari-ar' LIMIT 5"
```

```python
import duckdb
duckdb.sql("SELECT count(*) FROM 'hf://datasets/quranlab/hadith/bukhari-ar/*.parquet'")
```

## Quality, and how to check it yourself

Nothing is released until the integrity gate passes. Every claim below is
something you can re-run rather than take on trust — here on the published data,
not in our build tree:

| What is guaranteed | Evidence |
|---|---|
| Grades are attributed, never asserted by us | each grade carries its grader; the Arabic matn layer ships ungraded rather than auto-stamped, and a wrong-grade trap set exists to catch models that guess |
| One key across every language | `hadith_key` aligns the same hadith across all languages of a collection; 65,834 hadith on the Arabic spine, 13 collections |
| Arabic matn is public-domain text kept verbatim | no normalisation, no silent editing |
| Scope is enforced in code | non-Sunni collections and hostile-orientalist grade framings are refused by the builder from a machine-readable exclusion list, not by convention |
| Numbering is the source edition's | `hadith_number` is a string and follows the printed edition; `seq` is a contiguous 1..N spine so nothing silently reorders |

```python
from datasets import load_dataset

ar = load_dataset("quranlab/hadith", "bukhari-ar", split="train")
en = load_dataset("quranlab/hadith", "bukhari-en", split="train")

assert ar["hadith_key"] == en["hadith_key"]     # same key, any language

# every grade names the muhaddith who gave it
he = load_dataset("quranlab/hadith", "hadeethenc-en", split="train")
assert all(g and s for g, s in zip(he["grade"], he["grader"]))

# the ungraded matn layer stays ungraded, never auto-stamped
ah = load_dataset("quranlab/hadith", "ahmad-ar", split="train")
assert all(g is None for g in ah["grade"])
```

Where a source is genuinely missing, the row is published **empty and labelled**
rather than filled by guessing from a neighbouring entry. Coverage numbers in
this card count only real content.

## Citation

```bibtex
@misc{quranlab_hadith_2026,
  title        = {QuranLab — Hadith and Sunnah Corpus (Ahl al-Sunnah)},
  author       = {QuranLab},
  year         = {2026},
  publisher    = {Hugging Face},
  howpublished = {\url{https://huggingface.co/datasets/quranlab/hadith}}
}
```
