import FormControl from "@material-ui/core/FormControl";
import FormHelperText from "@material-ui/core/FormHelperText";
import InputLabel from "@material-ui/core/InputLabel";
import MenuItem from "@material-ui/core/MenuItem";
import Select, { SelectProps } from "@material-ui/core/Select";
import { withStyles } from "@material-ui/core/styles";
import * as React from "react";

const decorate = withStyles({
  formControl: {
    width: "100%"
  }
});

interface SingleSelectFieldProps {
  choices: Array<{
    value: string;
    label: string;
  }>;
  disabled?: boolean;
  error?: boolean;
  hint?: string;
  label?: string;
  name?: string;
  selectProps?: SelectProps;
  value?: string;
  onChange(event: any);
}

export const SingleSelectField = decorate<SingleSelectFieldProps>(
  ({
    classes,
    disabled,
    error,
    label,
    choices,
    value,
    onChange,
    name,
    hint,
    selectProps
  }) => {
    const choicesByKey: { [key: string]: string } =
      choices === undefined
        ? {}
        : choices.reduce((prev, curr) => {
            prev[curr.value] = curr.label;
            return prev;
          }, {});

    return (
      <FormControl
        className={classes.formControl}
        error={error}
        disabled={disabled}
      >
        <InputLabel shrink={!!value}>{label}</InputLabel>
        <Select
          fullWidth
          renderValue={choiceValue =>
            choiceValue ? choicesByKey[choiceValue.toString()] : ""
          }
          value={value || ""}
          name={name}
          onChange={onChange}
          {...selectProps}
        >
          {choices.map(choice => (
            <MenuItem value={choice.value} key={choice.value}>
              {choice.label}
            </MenuItem>
          ))}
        </Select>
        {hint && <FormHelperText>{hint}</FormHelperText>}
      </FormControl>
    );
  }
);

export default SingleSelectField;
