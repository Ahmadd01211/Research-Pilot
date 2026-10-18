import { z } from "zod";
export const loginSchema = z.object({ email: z.email("Enter a valid email address"), password: z.string().min(1, "Enter your password").max(128) });
export const registerSchema = loginSchema.extend({ password: z.string().min(12, "Use at least 12 characters").max(128), display_name: z.string().trim().min(1, "Enter your name").max(100) });
export const profileSchema = z.object({ display_name: z.string().trim().min(1, "Enter your name").max(100) });
