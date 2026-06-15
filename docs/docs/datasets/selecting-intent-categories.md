---
sidebar_position: 2
title: Selecting intent categories
---

# Selecting intent categories

Use `intents` when you want to build attack goals from the OmniSafeBench
risk taxonomy instead of manually providing `goals` or selecting a full
`dataset` provider.

This is useful when you want to:

- target specific risk families
- keep labels consistent in dashboard/results metadata
- skip category-classifier preflight when labels are explicitly provided

## Citation

The intent taxonomy used in this page is based on OmniSafeBench-MM:

- OmniSafeBench-MM repository: [jiaxiaojunQAQ/OmniSafeBench-MM](https://github.com/jiaxiaojunQAQ/OmniSafeBench-MM/)

## Three ways to write intents config

### 1. Full labels as strings

```python
attack_config = {
    "attack_type": "h4rm3l",
    "intents": [
        {
            "category": "Ethical and Social Risks",
            "subcategories": [
                "Bias and Discrimination",
                "Insulting or Harassing Speech",
            ],
            "samples_per_subcategory": 2,
        },
        {
            "category": "Decision and Cognitive Risks",
            "subcategories": ["Medical Advice"],
            "samples_per_subcategory": 2,
        },
    ],
}
```

### 2. Enums

```python
from hackagent.datasets import IntentCategory, IntentSubcategory

attack_config = {
    "attack_type": "h4rm3l",
    "intents": [
        {
            "category": IntentCategory.ETHICAL_AND_SOCIAL_RISKS,
            "subcategories": [
                IntentSubcategory.BIAS_AND_DISCRIMINATION,
                IntentSubcategory.INSULTING_OR_HARASSING_SPEECH,
            ],
            "samples_per_subcategory": 2,
        },
        {
            "category": IntentCategory.DECISION_AND_COGNITIVE_RISKS,
            "subcategories": [IntentSubcategory.MEDICAL_ADVICE],
            "samples_per_subcategory": 2,
        },
    ],
}
```

### 3. Label codes as strings

```python
attack_config = {
    "attack_type": "h4rm3l",
    "intents": [
        {
            "category": "A",
            "subcategories": ["A1", "A2"],
            "samples_per_subcategory": 2,
        },
        {
            "category": "I",
            "subcategories": ["I1"],
            "samples_per_subcategory": 2,
        },
    ],
}
```

## Default behavior for omitted fields

When some fields are omitted in an `intents` entry, HackAgent applies the
following defaults:

- If `subcategories` is not provided, all subcategories of the selected
    category are used.
- If `samples_per_subcategory` is not provided, the default is `1` sample
    for each selected subcategory.
- Therefore, if both are omitted, HackAgent selects `1` sample for all
    subcategories in the selected category.

Example:

```python
attack_config = {
        "attack_type": "h4rm3l",
        "intents": [
                {
                        "category": "A",
                        # subcategories omitted -> A1..A4
                        # samples_per_subcategory omitted -> 1 each
                }
        ],
}
```

## Complete taxonomy map (code, label, enum ID)

Source taxonomy and intents list: [OmniSafeBench-MM](https://github.com/jiaxiaojunQAQ/OmniSafeBench-MM/).

<table style="width: 100%; border-collapse: collapse;">
<thead>
<tr>
<th style="text-align: left; padding: 8px; border-bottom: 2px solid var(--ifm-color-emphasis-400);">Code</th>
<th style="text-align: left; padding: 8px; border-bottom: 2px solid var(--ifm-color-emphasis-400);">Name</th>
<th style="text-align: left; padding: 8px; border-bottom: 2px solid var(--ifm-color-emphasis-400);">Enum ID</th>
<th style="text-align: right; padding: 8px; border-bottom: 2px solid var(--ifm-color-emphasis-400);">Samples</th>
</tr>
</thead>
<tbody>
<tr style="border-top: 3px solid var(--ifm-color-emphasis-500);"><td style="padding: 8px;"><strong>A</strong></td><td style="padding: 8px;"><strong>Ethical and Social Risks</strong></td><td style="padding: 8px;"><strong>IntentCategory.ETHICAL_AND_SOCIAL_RISKS</strong></td><td style="padding: 8px; text-align: right;"><strong>988</strong></td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">A1</td><td style="padding: 8px;">Bias and Discrimination</td><td style="padding: 8px;">IntentSubcategory.BIAS_AND_DISCRIMINATION</td><td style="padding: 8px; text-align: right;">434</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">A2</td><td style="padding: 8px;">Insulting or Harassing Speech</td><td style="padding: 8px;">IntentSubcategory.INSULTING_OR_HARASSING_SPEECH</td><td style="padding: 8px; text-align: right;">113</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">A3</td><td style="padding: 8px;">Hate Speech</td><td style="padding: 8px;">IntentSubcategory.HATE_SPEECH</td><td style="padding: 8px; text-align: right;">411</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">A4</td><td style="padding: 8px;">Discriminatory Behavior</td><td style="padding: 8px;">IntentSubcategory.DISCRIMINATORY_BEHAVIOR</td><td style="padding: 8px; text-align: right;">30</td></tr>
<tr style="border-top: 3px solid var(--ifm-color-emphasis-500);"><td style="padding: 8px;"><strong>B</strong></td><td style="padding: 8px;"><strong>Privacy and Data Risks</strong></td><td style="padding: 8px;"><strong>IntentCategory.PRIVACY_AND_DATA_RISKS</strong></td><td style="padding: 8px; text-align: right;"><strong>504</strong></td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">B1</td><td style="padding: 8px;">Personal Data Leakage</td><td style="padding: 8px;">IntentSubcategory.PERSONAL_DATA_LEAKAGE</td><td style="padding: 8px; text-align: right;">250</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">B2</td><td style="padding: 8px;">Biometric or Health Data Exposure</td><td style="padding: 8px;">IntentSubcategory.BIOMETRIC_OR_HEALTH_DATA_EXPOSURE</td><td style="padding: 8px; text-align: right;">30</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">B3</td><td style="padding: 8px;">Doxxing or Tracking</td><td style="padding: 8px;">IntentSubcategory.DOXXING_OR_TRACKING</td><td style="padding: 8px; text-align: right;">164</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">B4</td><td style="padding: 8px;">Surveillance Misuse</td><td style="padding: 8px;">IntentSubcategory.SURVEILLANCE_MISUSE</td><td style="padding: 8px; text-align: right;">30</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">B5</td><td style="padding: 8px;">Training Data Leakage</td><td style="padding: 8px;">IntentSubcategory.TRAINING_DATA_LEAKAGE</td><td style="padding: 8px; text-align: right;">30</td></tr>
<tr style="border-top: 3px solid var(--ifm-color-emphasis-500);"><td style="padding: 8px;"><strong>C</strong></td><td style="padding: 8px;"><strong>Safety and Physical Harm</strong></td><td style="padding: 8px;"><strong>IntentCategory.SAFETY_AND_PHYSICAL_HARM</strong></td><td style="padding: 8px; text-align: right;"><strong>877</strong></td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">C1</td><td style="padding: 8px;">Dangerous Instructions</td><td style="padding: 8px;">IntentSubcategory.DANGEROUS_INSTRUCTIONS</td><td style="padding: 8px; text-align: right;">29</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">C3</td><td style="padding: 8px;">Physical Harm</td><td style="padding: 8px;">IntentSubcategory.PHYSICAL_HARM</td><td style="padding: 8px; text-align: right;">599</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">C4</td><td style="padding: 8px;">Human Trafficking</td><td style="padding: 8px;">IntentSubcategory.HUMAN_TRAFFICKING</td><td style="padding: 8px; text-align: right;">30</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">C2</td><td style="padding: 8px;">Self-harm Promotion</td><td style="padding: 8px;">IntentSubcategory.SELF_HARM_PROMOTION</td><td style="padding: 8px; text-align: right;">30</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">C5</td><td style="padding: 8px;">Animal Abuse</td><td style="padding: 8px;">IntentSubcategory.ANIMAL_ABUSE</td><td style="padding: 8px; text-align: right;">132</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">C6</td><td style="padding: 8px;">Drug Guidance</td><td style="padding: 8px;">IntentSubcategory.DRUG_GUIDANCE</td><td style="padding: 8px; text-align: right;">29</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">C7</td><td style="padding: 8px;">Environmental Damage</td><td style="padding: 8px;">IntentSubcategory.ENVIRONMENTAL_DAMAGE</td><td style="padding: 8px; text-align: right;">28</td></tr>
<tr style="border-top: 3px solid var(--ifm-color-emphasis-500);"><td style="padding: 8px;"><strong>D</strong></td><td style="padding: 8px;"><strong>Criminal and Economic Risks</strong></td><td style="padding: 8px;"><strong>IntentCategory.CRIMINAL_AND_ECONOMIC_RISKS</strong></td><td style="padding: 8px; text-align: right;"><strong>1017</strong></td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">D1</td><td style="padding: 8px;">Fraud or Scams</td><td style="padding: 8px;">IntentSubcategory.FRAUD_OR_SCAMS</td><td style="padding: 8px; text-align: right;">367</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">D2</td><td style="padding: 8px;">Economic Crime</td><td style="padding: 8px;">IntentSubcategory.ECONOMIC_CRIME</td><td style="padding: 8px; text-align: right;">245</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">D3</td><td style="padding: 8px;">White-Collar Crime</td><td style="padding: 8px;">IntentSubcategory.WHITE_COLLAR_CRIME</td><td style="padding: 8px; text-align: right;">30</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">D4</td><td style="padding: 8px;">Illegal Activity</td><td style="padding: 8px;">IntentSubcategory.ILLEGAL_ACTIVITY</td><td style="padding: 8px; text-align: right;">345</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">D5</td><td style="padding: 8px;">Evasion of Law</td><td style="padding: 8px;">IntentSubcategory.EVASION_OF_LAW</td><td style="padding: 8px; text-align: right;">30</td></tr>
<tr style="border-top: 3px solid var(--ifm-color-emphasis-500);"><td style="padding: 8px;"><strong>E</strong></td><td style="padding: 8px;"><strong>Cybersecurity Threats</strong></td><td style="padding: 8px;"><strong>IntentCategory.CYBERSECURITY_THREATS</strong></td><td style="padding: 8px; text-align: right;"><strong>725</strong></td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">E1</td><td style="padding: 8px;">Malware Generation</td><td style="padding: 8px;">IntentSubcategory.MALWARE_GENERATION</td><td style="padding: 8px; text-align: right;">275</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">E2</td><td style="padding: 8px;">Exploit Development</td><td style="padding: 8px;">IntentSubcategory.EXPLOIT_DEVELOPMENT</td><td style="padding: 8px; text-align: right;">201</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">E3</td><td style="padding: 8px;">Phishing or Ransomware</td><td style="padding: 8px;">IntentSubcategory.PHISHING_OR_RANSOMWARE</td><td style="padding: 8px; text-align: right;">30</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">E4</td><td style="padding: 8px;">Jailbreak or Prompt Injection</td><td style="padding: 8px;">IntentSubcategory.JAILBREAK_OR_PROMPT_INJECTION</td><td style="padding: 8px; text-align: right;">30</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">E5</td><td style="padding: 8px;">Cross-modal Attack</td><td style="padding: 8px;">IntentSubcategory.CROSS_MODAL_ATTACK</td><td style="padding: 8px; text-align: right;">30</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">E6</td><td style="padding: 8px;">Data Poisoning</td><td style="padding: 8px;">IntentSubcategory.DATA_POISONING</td><td style="padding: 8px; text-align: right;">30</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">E7</td><td style="padding: 8px;">Unauthorized Model Access</td><td style="padding: 8px;">IntentSubcategory.UNAUTHORIZED_MODEL_ACCESS</td><td style="padding: 8px; text-align: right;">129</td></tr>
<tr style="border-top: 3px solid var(--ifm-color-emphasis-500);"><td style="padding: 8px;"><strong>F</strong></td><td style="padding: 8px;"><strong>Information and Political Manipulation</strong></td><td style="padding: 8px;"><strong>IntentCategory.INFORMATION_AND_POLITICAL_MANIPULATION</strong></td><td style="padding: 8px; text-align: right;"><strong>534</strong></td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">F1</td><td style="padding: 8px;">Misinformation or Disinformation</td><td style="padding: 8px;">IntentSubcategory.MISINFORMATION_OR_DISINFORMATION</td><td style="padding: 8px; text-align: right;">30</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">F2</td><td style="padding: 8px;">Deepfakes or Synthetic Media</td><td style="padding: 8px;">IntentSubcategory.DEEPFAKES_OR_SYNTHETIC_MEDIA</td><td style="padding: 8px; text-align: right;">30</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">F3</td><td style="padding: 8px;">Political Propaganda</td><td style="padding: 8px;">IntentSubcategory.POLITICAL_PROPAGANDA</td><td style="padding: 8px; text-align: right;">384</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">F4</td><td style="padding: 8px;">Election Interference</td><td style="padding: 8px;">IntentSubcategory.ELECTION_INTERFERENCE</td><td style="padding: 8px; text-align: right;">30</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">F5</td><td style="padding: 8px;">Public Order Disruption</td><td style="padding: 8px;">IntentSubcategory.PUBLIC_ORDER_DISRUPTION</td><td style="padding: 8px; text-align: right;">30</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">F6</td><td style="padding: 8px;">National Security Threat</td><td style="padding: 8px;">IntentSubcategory.NATIONAL_SECURITY_THREAT</td><td style="padding: 8px; text-align: right;">30</td></tr>
<tr style="border-top: 3px solid var(--ifm-color-emphasis-500);"><td style="padding: 8px;"><strong>G</strong></td><td style="padding: 8px;"><strong>Content and Cultural Safety</strong></td><td style="padding: 8px;"><strong>IntentCategory.CONTENT_AND_CULTURAL_SAFETY</strong></td><td style="padding: 8px; text-align: right;"><strong>537</strong></td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">G1</td><td style="padding: 8px;">Pornography or Nudity</td><td style="padding: 8px;">IntentSubcategory.PORNOGRAPHY_OR_NUDITY</td><td style="padding: 8px; text-align: right;">118</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">G2</td><td style="padding: 8px;">Sexual Content</td><td style="padding: 8px;">IntentSubcategory.SEXUAL_CONTENT</td><td style="padding: 8px; text-align: right;">137</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">G3</td><td style="padding: 8px;">Violence or Gore</td><td style="padding: 8px;">IntentSubcategory.VIOLENCE_OR_GORE</td><td style="padding: 8px; text-align: right;">152</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">G4</td><td style="padding: 8px;">Cultural or Religious Offense</td><td style="padding: 8px;">IntentSubcategory.CULTURAL_OR_RELIGIOUS_OFFENSE</td><td style="padding: 8px; text-align: right;">130</td></tr>
<tr style="border-top: 3px solid var(--ifm-color-emphasis-500);"><td style="padding: 8px;"><strong>H</strong></td><td style="padding: 8px;"><strong>Intellectual Property and Ownership</strong></td><td style="padding: 8px;"><strong>IntentCategory.INTELLECTUAL_PROPERTY_AND_OWNERSHIP</strong></td><td style="padding: 8px; text-align: right;"><strong>304</strong></td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">H1</td><td style="padding: 8px;">Copyright Infringement</td><td style="padding: 8px;">IntentSubcategory.COPYRIGHT_INFRINGEMENT</td><td style="padding: 8px; text-align: right;">117</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">H2</td><td style="padding: 8px;">Trademark or Brand Misuse</td><td style="padding: 8px;">IntentSubcategory.TRADEMARK_OR_BRAND_MISUSE</td><td style="padding: 8px; text-align: right;">30</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">H3</td><td style="padding: 8px;">Proprietary Data Leakage</td><td style="padding: 8px;">IntentSubcategory.PROPRIETARY_DATA_LEAKAGE</td><td style="padding: 8px; text-align: right;">127</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">H4</td><td style="padding: 8px;">Unauthorized Style or Persona Imitation</td><td style="padding: 8px;">IntentSubcategory.UNAUTHORIZED_STYLE_OR_PERSONA_IMITATION</td><td style="padding: 8px; text-align: right;">30</td></tr>
<tr style="border-top: 3px solid var(--ifm-color-emphasis-500);"><td style="padding: 8px;"><strong>I</strong></td><td style="padding: 8px;"><strong>Decision and Cognitive Risks</strong></td><td style="padding: 8px;"><strong>IntentCategory.DECISION_AND_COGNITIVE_RISKS</strong></td><td style="padding: 8px; text-align: right;"><strong>1593</strong></td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">I1</td><td style="padding: 8px;">Medical Advice</td><td style="padding: 8px;">IntentSubcategory.MEDICAL_ADVICE</td><td style="padding: 8px; text-align: right;">321</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">I2</td><td style="padding: 8px;">Health Misguidance</td><td style="padding: 8px;">IntentSubcategory.HEALTH_MISGUIDANCE</td><td style="padding: 8px; text-align: right;">128</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">I3</td><td style="padding: 8px;">Legal Advice</td><td style="padding: 8px;">IntentSubcategory.LEGAL_ADVICE</td><td style="padding: 8px; text-align: right;">372</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">I4</td><td style="padding: 8px;">Government Decision Support</td><td style="padding: 8px;">IntentSubcategory.GOVERNMENT_DECISION_SUPPORT</td><td style="padding: 8px; text-align: right;">308</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">I5</td><td style="padding: 8px;">Financial Advice</td><td style="padding: 8px;">IntentSubcategory.FINANCIAL_ADVICE</td><td style="padding: 8px; text-align: right;">290</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">I6</td><td style="padding: 8px;">Market Manipulation</td><td style="padding: 8px;">IntentSubcategory.MARKET_MANIPULATION</td><td style="padding: 8px; text-align: right;">30</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">I7</td><td style="padding: 8px;">Psychological Manipulation</td><td style="padding: 8px;">IntentSubcategory.PSYCHOLOGICAL_MANIPULATION</td><td style="padding: 8px; text-align: right;">114</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">I8</td><td style="padding: 8px;">Cognitive Bias or Overreliance</td><td style="padding: 8px;">IntentSubcategory.COGNITIVE_BIAS_OR_OVERRELIANCE</td><td style="padding: 8px; text-align: right;">30</td></tr>
<tr style="border-top: 3px solid var(--ifm-color-emphasis-500);"><td style="padding: 8px;"><strong>J</strong></td><td style="padding: 8px;"><strong>Child Safety</strong></td><td style="padding: 8px;"><strong>IntentCategory.CHILD_SAFETY</strong></td><td style="padding: 8px; text-align: right;"><strong>747</strong></td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">J1</td><td style="padding: 8px;">CSAM & Sexualization</td><td style="padding: 8px;">IntentSubcategory.CSAM_SEXUALIZATION</td><td style="padding: 8px; text-align: right;">171</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">J2</td><td style="padding: 8px;">Grooming & Enticement</td><td style="padding: 8px;">IntentSubcategory.GROOMING_ENTICEMENT</td><td style="padding: 8px; text-align: right;">147</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">J3</td><td style="padding: 8px;">Child Trafficking</td><td style="padding: 8px;">IntentSubcategory.CHILD_TRAFFICKING</td><td style="padding: 8px; text-align: right;">144</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">J4</td><td style="padding: 8px;">Harmful Content Targeting Minors</td><td style="padding: 8px;">IntentSubcategory.HARMFUL_CONTENT_TARGETING_MINORS</td><td style="padding: 8px; text-align: right;">161</td></tr>
<tr style="border-top: 1px solid var(--ifm-color-emphasis-300);"><td style="padding: 8px;">J5</td><td style="padding: 8px;">Age Verification Evasion</td><td style="padding: 8px;">IntentSubcategory.AGE_VERIFICATION_EVASION</td><td style="padding: 8px; text-align: right;">124</td></tr>
</tbody>
</table>
