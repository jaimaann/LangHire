interface FormFieldProps {
  label: string;
  children: React.ReactNode;
  hint?: string;
  className?: string;
}

export default function FormField({ label, children, hint, className = "" }: FormFieldProps) {
  return (
    <div className={className}>
      <label className="block text-sm font-semibold text-foreground mb-1.5">{label}</label>
      {children}
      {hint && <p className="text-[13px] text-muted-foreground mt-1.5">{hint}</p>}
    </div>
  );
}

interface InputFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
}

export function InputField({ label, value, onChange, type = "text", placeholder, className = "", disabled }: InputFieldProps) {
  return (
    <FormField label={label} className={className}>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className="input-base"
      />
    </FormField>
  );
}
