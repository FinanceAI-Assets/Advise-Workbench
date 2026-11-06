// Library management: the choices and defaults of a practice's details.

export const TAXONOMY = ["Operating model", "Transformation", "Risk & controls", "Change & adoption", "Procurement", "Finance", "Technology"];
export const MATURITY = ["Emerging", "Defined", "Managed", "Optimized"];
export const CLASSIFICATION = ["Internal methods content", "Confidential", "Public reference"];

/** The details entered on Create practice. */
export type PracticeDetails = {
  title: string;
  taxonomy: string;
  maturity: string;
  version: string;
  owner: string;
  classification: string;
  rights: string;
  description: string;
};

export const EMPTY_PRACTICE: PracticeDetails = {
  title: "",
  taxonomy: TAXONOMY[0],
  maturity: "Defined",
  version: "v1.0",
  owner: "",
  classification: CLASSIFICATION[0],
  rights: "Advisory Methods team · Internal reuse permitted",
  description: "",
};
