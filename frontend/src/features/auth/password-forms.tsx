import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { ArrowRight, CheckCircle2, KeyRound, LoaderCircle, LockKeyhole, MailCheck } from 'lucide-react';
import type { z } from 'zod';
import { mutate } from '@/lib/api/client';
import { changePasswordSchema, forgotPasswordSchema, resetPasswordSchema } from './schemas';
import { PasswordField } from './password-field';

type ForgotValues = z.infer<typeof forgotPasswordSchema>;
type ResetValues = z.infer<typeof resetPasswordSchema>;
type ChangeValues = z.infer<typeof changePasswordSchema>;
const failed = (failure: unknown, fallback: string) => failure instanceof Error ? failure.message : fallback;

export function ForgotPasswordForm() {
  const [error, setError] = useState(''), [sentTo, setSentTo] = useState('');
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<ForgotValues>({ resolver: zodResolver(forgotPasswordSchema) });
  async function submit(data: ForgotValues) {
    setError('');
    try { await mutate('/auth/password/forgot', 'POST', data); setSentTo(data.email); }
    catch (failure) { setError(failed(failure, 'Unable to send a reset link. Please try again.')); }
  }
  if (sentTo) return <div className="auth-card"><p className="eyebrow">CHECK YOUR INBOX</p><h2>Reset link on its way.</h2><p role="status" className="notice mt24"><MailCheck size={16}/>If an account exists for {sentTo}, we have emailed a link to choose a new password. It works once and expires shortly.</p><p className="switch">Remembered it? <Link to="/login">Back to sign in</Link></p></div>;
  return <div className="auth-card"><p className="eyebrow">ACCOUNT RECOVERY</p><h2>Forgot your password?</h2><p className="muted">Enter the email for your account and we will send you a link to choose a new one.</p><form onSubmit={handleSubmit(submit)} noValidate><label className="field">Email address<input type="email" autoComplete="email" {...register('email')} aria-invalid={!!errors.email} aria-describedby="email-error"/><small id="email-error" className="field-error">{errors.email?.message}</small></label>{error && <p role="alert" className="alert">{error}</p>}<button className="btn primary full" type="submit" disabled={isSubmitting}>{isSubmitting ? <LoaderCircle className="spin" size={16}/> : null}{isSubmitting ? 'Sending…' : 'Send reset link'}{!isSubmitting && <ArrowRight size={16}/>}</button></form><p className="switch">Remembered it? <Link to="/login">Back to sign in</Link></p><p className="security-note"><LockKeyhole size={13}/>For your privacy we show the same message whether or not an account exists.</p></div>;
}

export function ResetPasswordForm() {
  const location = useLocation(), navigate = useNavigate(), queryClient = useQueryClient(), [error, setError] = useState('');
  // The emailed token is in the URL fragment; keep it in memory and remove it from the address bar.
  const [token] = useState(() => new URLSearchParams(location.hash.slice(1)).get('token') ?? '');
  useEffect(() => { if (location.hash) void navigate(location.pathname, { replace: true }); }, [location.hash, location.pathname, navigate]);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<ResetValues>({ resolver: zodResolver(resetPasswordSchema) });
  async function submit(data: ResetValues) {
    setError('');
    try { await mutate('/auth/password/reset', 'POST', { token, new_password: data.new_password }); queryClient.clear(); void navigate('/login?reset=1', { replace: true }); }
    catch (failure) { setError(failed(failure, 'Unable to reset your password. Please try again.')); }
  }
  if (!token) return <div className="auth-card"><p className="eyebrow">ACCOUNT RECOVERY</p><h2>This reset link is incomplete.</h2><p className="muted">Open the full link from your email, or request a new one.</p><Link className="btn primary full mt24" to="/forgot-password">Request a new link<ArrowRight size={16}/></Link></div>;
  return <div className="auth-card"><p className="eyebrow">ACCOUNT RECOVERY</p><h2>Choose a new password.</h2><p className="muted">You will be signed out everywhere and can then sign in with the new password.</p><form onSubmit={handleSubmit(submit)} noValidate><PasswordField id="reset-new" label="New password" field={register('new_password')} autoComplete="new-password" error={errors.new_password?.message} help="Use at least 12 characters."/><PasswordField id="reset-confirm" label="Confirm new password" field={register('confirm_password')} autoComplete="new-password" error={errors.confirm_password?.message}/>{error && <p role="alert" className="alert">{error} <Link to="/forgot-password">Request a new link</Link></p>}<button className="btn primary full" type="submit" disabled={isSubmitting}>{isSubmitting ? <LoaderCircle className="spin" size={16}/> : <KeyRound size={16}/>}{isSubmitting ? 'Saving…' : 'Set new password'}</button></form></div>;
}

export function ChangePasswordForm() {
  const [error, setError] = useState(''), [notice, setNotice] = useState('');
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<ChangeValues>({ resolver: zodResolver(changePasswordSchema) });
  async function save(data: ChangeValues) {
    setError(''); setNotice('');
    try { await mutate('/me/password', 'POST', { current_password: data.current_password, new_password: data.new_password }); reset(); setNotice('Password changed. Other devices have been signed out.'); }
    catch (failure) { setError(failed(failure, 'Unable to change your password')); }
  }
  return <section className="card profile-card password-card"><div className="card-heading"><h2>Password</h2><p className="muted">Changing your password keeps this device signed in and signs out every other session.</p></div><form onSubmit={handleSubmit(save)} noValidate><PasswordField id="current-password" label="Current password" field={register('current_password')} autoComplete="current-password" error={errors.current_password?.message}/><PasswordField id="new-password" label="New password" field={register('new_password')} autoComplete="new-password" error={errors.new_password?.message} help="Use at least 12 characters."/><PasswordField id="confirm-password" label="Confirm new password" field={register('confirm_password')} autoComplete="new-password" error={errors.confirm_password?.message}/>{error && <p role="alert" className="alert">{error}</p>}{notice && <p role="status" className="notice"><CheckCircle2 size={16}/>{notice}</p>}<div className="form-footer"><span className="muted tiny">Forgot it? Sign out and use “Forgot password?” on the sign-in page.</span><button className="btn primary" disabled={isSubmitting}>{isSubmitting ? <LoaderCircle className="spin" size={16}/> : <KeyRound size={16}/>} {isSubmitting ? 'Changing…' : 'Change password'}</button></div></form></section>;
}
