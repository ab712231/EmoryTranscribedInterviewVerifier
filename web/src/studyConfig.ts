export interface StudyDetails {
  retentionPeriod: string;
  studyTeamContact: string;
}

export const STUDY: StudyDetails = {
  retentionPeriod: "",
  studyTeamContact: "",
};

export function missingStudyDetails(details: StudyDetails = STUDY): string[] {
  const missing: string[] = [];
  for (const [key, value] of Object.entries(details)) {
    if (!String(value).trim()) missing.push(key);
  }
  return missing;
}
