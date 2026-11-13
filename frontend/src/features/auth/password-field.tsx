import { useState } from 'react';
import type { UseFormRegisterReturn } from 'react-hook-form';
import { Eye, EyeOff } from 'lucide-react';
type Props = { id: string; label: string; field: UseFormRegisterReturn; autoComplete: 'current-password' | 'new-password'; error?: string; help?: string };
export function PasswordField({ id, label, field, autoComplete, error, help = '' }: Props) {
  const [visible, setVisible] = useState(false);
  return <div className="field"><label htmlFor={id}>{label}</label><div className="password-wrap"><input id={id} type={visible ? 'text' : 'password'} autoComplete={autoComplete} {...field} aria-invalid={!!error} aria-describedby={`${id}-help`}/><button type="button" className="icon-button" aria-label={visible ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`} onClick={() => setVisible(!visible)}>{visible ? <EyeOff size={17}/> : <Eye size={17}/>}</button></div><small id={`${id}-help`} className={error ? 'field-error' : 'muted'}>{error || help}</small></div>;
}
