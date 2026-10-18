import { z } from 'zod';
export function lines(value: string): string[] { return value.split('\n').map(s => s.trim()).filter(Boolean); }
const researchText = z.string().refine(value => lines(value).length <= 20, 'Use no more than 20 entries.').refine(value => lines(value).every(line => line.length <= 500), 'Keep each entry within 500 characters.');
export const projectFormSchema = z.object({ title: z.string().trim().min(1, 'Give your project a title.').max(160, 'Use at most 160 characters.'), description: z.string().trim().max(4000, 'Use at most 4,000 characters.'), research_questions: researchText, objectives: researchText });
export type ProjectFormValues = z.infer<typeof projectFormSchema>;
export function projectFields(values: ProjectFormValues) { return { title: values.title.trim(), description: values.description.trim(), research_questions: lines(values.research_questions), objectives: lines(values.objectives) }; }
