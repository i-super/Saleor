import FormControl from "@material-ui/core/FormControl";
import FormHelperText from "@material-ui/core/FormHelperText";
import Input from "@material-ui/core/Input";
import InputLabel from "@material-ui/core/InputLabel";
import * as React from "react";

interface RichTextEditorProps {
  defaultValue?: string;
  disabled?: boolean;
  error?: boolean;
  fullWidth?: boolean;
  helperText: string;
  label?: string;
  name: string;
  value?: string;
  onChange(event: any);
}

export const RichTextEditor: React.StatelessComponent<RichTextEditorProps> = ({
  defaultValue,
  disabled,
  error,
  fullWidth,
  helperText,
  label,
  name,
  onChange,
  value
}) => (
  <FormControl style={fullWidth ? { width: "100%" } : {}} error={error}>
    {label && (
      <InputLabel shrink={!!(value || defaultValue)}>{label}</InputLabel>
    )}
    <Input
      disabled={disabled}
      multiline
      name={name}
      {...(value ? { value } : {})}
      {...(defaultValue ? { defaultValue } : {})}
      onChange={onChange}
      fullWidth={fullWidth}
    />
    {helperText && <FormHelperText>{helperText}</FormHelperText>}
  </FormControl>
);

export default RichTextEditor;
