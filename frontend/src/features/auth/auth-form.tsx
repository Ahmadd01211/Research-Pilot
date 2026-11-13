import { Link, useLocation, useNavigate } from 'react-router';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { ArrowRight, LoaderCircle, LockKeyhole } from 'lucide-react';
import type { z } from 'zod';
import { mutate, type User } from '@/lib/api/client';
import { loginSchema, registerSchema } from './schemas';
import { sessionKey } from './use-session';
import { PasswordField } from './password-field';

type LoginValues = z.infer<typeof loginSchema>;
type RegisterValues = z.infer<typeof registerSchema>;
function FormHeading({ registering }: { registering: boolean }) {
  return <><p className="eyebrow">{registering ? 'YOUR RESEARCH STARTS HERE' : 'WELCOME BACK TO YOUR WORK'}</p><h2>{registering ? 'Create your research space.' : 'Good to have you back.'}</h2><p className="muted">{registering ? 'A focused home for your papers, evidence, and ideas.' : 'Sign in to continue where your thinking left off.'}</p></>;
}
export function LoginForm() {
  const location = useLocation();
  const returnTo: unknown = location.state?.returnTo;
  const destination = typeof returnTo === 'string' && /^\/(?:dashboard|profile|projects|find-evidence|write)(?:[/?#]|$)/.test(returnTo) && !returnTo.includes('\\') && [...returnTo].every(character => character.charCodeAt(0) >= 32) ? returnTo : '/dashboard';
  const navigate = useNavigate(), queryClient = useQueryClient(), [error, setError] = useState('');
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) });
  async function submit(data: LoginValues) {
    setError('');
    try {
      const user = await mutate<User>('/auth/login', 'POST', data);
      queryClient.clear(); queryClient.setQueryData(sessionKey, user); navigate(destination, { replace: true });
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Unable to sign in. Please try again.'); }
  }
  return <div className="auth-card"><FormHeading registering={false}/><form onSubmit={handleSubmit(submit)} noValidate><label className="field">Email address<input type="email" autoComplete="email" {...register('email')} aria-invalid={!!errors.email} aria-describedby="email-error"/><small id="email-error" className="field-error">{errors.email?.message}</small></label><PasswordField id="auth-password" label="Password" field={register('password')} autoComplete="current-password" error={errors.password?.message}/><Link className="forgot-link" to="/forgot-password">Forgot password?</Link>{error && <p role="alert" className="alert">{error}</p>}<button className="btn primary full" type="submit" disabled={isSubmitting}>{isSubmitting ? <LoaderCircle className="spin" size={16}/> : null}{isSubmitting ? 'Signing in…' : 'Sign in'}{!isSubmitting && <ArrowRight size={16}/>}</button></form><p className="switch">New to ResearchPilot? <Link to="/register">Create an account</Link></p><p className="security-note"><LockKeyhole size={13}/>Secure, revocable session. Your password stays private.</p></div>;
}
export function RegisterForm() {
  const navigate = useNavigate(), [error, setError] = useState('');
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<RegisterValues>({ resolver: zodResolver(registerSchema) });
  async function submit(data: RegisterValues) {
    setError('');
    try { await mutate<User>('/auth/register', 'POST', data); navigate('/login?registered=1', { replace: true }); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Unable to create the account. Please try again.'); }
  }
  return <div className="auth-card"><FormHeading registering/><form onSubmit={handleSubmit(submit)} noValidate><label className="field">Full name<input autoComplete="name" {...register('display_name')} aria-invalid={!!errors.display_name} aria-describedby="name-error"/><small id="name-error" className="field-error">{errors.display_name?.message}</small></label><label className="field">Email address<input type="email" autoComplete="email" {...register('email')} aria-invalid={!!errors.email} aria-describedby="email-error"/><small id="email-error" className="field-error">{errors.email?.message}</small></label><PasswordField id="auth-password" label="Password" field={register('password')} autoComplete="new-password" error={errors.password?.message} help="Use at least 12 characters."/>{error && <p role="alert" className="alert">{error}</p>}<button type="submit" className="btn primary full" disabled={isSubmitting}>{isSubmitting ? <LoaderCircle className="spin" size={16}/> : null}{isSubmitting ? 'Creating account…' : 'Create account'}{!isSubmitting && <ArrowRight size={16}/>}</button></form><p className="switch">Already have an account? <Link to="/login">Sign in</Link></p><p className="security-note"><LockKeyhole size={13}/>Your research journey starts with a private account.</p></div>;
}
