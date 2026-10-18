import { describe, expect, it } from "vitest";
import { loginSchema, profileSchema, registerSchema } from "../src/features/auth/schemas";
describe("identity form validation", () => {
  it("rejects short passwords and blank names at registration", () => {
    expect(registerSchema.safeParse({email:"researcher@example.com",password:"short",display_name:"R"}).success).toBe(false);
    expect(registerSchema.safeParse({email:"researcher@example.com",password:"long-valid-password",display_name:"  "}).success).toBe(false);
  });
  it("permits login without changing established credentials", () => {
    expect(loginSchema.safeParse({email:"researcher@example.com",password:"short"}).success).toBe(true);
  });
  it("trims names and rejects empty profile edits", () => {
    expect(profileSchema.parse({display_name:"  Researcher  "}).display_name).toBe("Researcher");
    expect(profileSchema.safeParse({display_name:"  "}).success).toBe(false);
  });
});
