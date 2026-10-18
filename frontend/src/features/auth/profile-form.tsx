import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, LoaderCircle, LogOut, Save } from 'lucide-react';
import { mutate, type User } from '@/lib/api/client';
import { profileSchema } from './schemas';
import { sessionKey } from './use-session';
export function ProfileForm({ user }: { user: User }) {
  const navigate = useNavigate(), queryClient = useQueryClient(), [error, setError] = useState(''), [notice, setNotice] = useState(''), [loggingOut, setLoggingOut] = useState(false);
  const { register, handleSubmit, formState: { errors, isSubmitting, isDirty }, reset } = useForm({ resolver: zodResolver(profileSchema), defaultValues: { display_name: user.display_name } });
  async function save(data: { display_name: string }) {
    setError(''); setNotice('');
    try { const updated = await mutate<User>('/me', 'PATCH', data); queryClient.setQueryData(sessionKey, updated); reset({ display_name: updated.display_name }); setNotice('Your profile has been saved.'); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Unable to save'); }
  }
  async function logout() {
    setLoggingOut(true); setError('');
    try { await mutate('/auth/logout', 'POST'); queryClient.clear(); queryClient.setQueryData(sessionKey, null); navigate('/login', { replace: true }); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Unable to sign out'); setLoggingOut(false); }
  }
  return <><section className="card profile-card"><div className="card-heading"><h2>Personal information</h2><p className="muted">Your name identifies your account. Your email is shown for reference.</p></div><div className="profile-identity"><span className="avatar large" aria-hidden="true">{user.display_name.split(' ').filter(Boolean).slice(0,2).map(s => s[0]).join('')}</span><div><strong>{user.display_name}</strong><p className="muted">{user.email}</p></div></div><form onSubmit={handleSubmit(save)} noValidate><label className="field">Display name<input autoComplete="name" {...register('display_name')} aria-invalid={!!errors.display_name} aria-describedby="name-error"/><small id="name-error" className="field-error">{errors.display_name?.message}</small></label><label className="field">Email address<input value={user.email} readOnly aria-describedby="email-help"/><small id="email-help" className="muted">Email changes are not available in this first feature.</small></label>{error && <p role="alert" className="alert">{error}</p>}{notice && <p role="status" className="notice"><CheckCircle2 size={16}/>{notice}</p>}<div className="form-footer"><span className="muted tiny">{isDirty ? 'You have unsaved changes.' : 'Your profile is up to date.'}</span><button className="btn primary" disabled={isSubmitting || loggingOut || !isDirty}>{isSubmitting ? <LoaderCircle className="spin" size={16}/> : <Save size={16}/>} {isSubmitting ? 'Saving…' : 'Save changes'}</button></div></form></section><section className="card signout"><div><h2>End this session</h2><p className="muted">Revoke this device’s session and return to sign in.</p></div><button className="btn" onClick={logout} disabled={loggingOut || isSubmitting}><LogOut size={16}/>{loggingOut ? 'Signing out…' : 'Sign out'}</button></section></>;
}
