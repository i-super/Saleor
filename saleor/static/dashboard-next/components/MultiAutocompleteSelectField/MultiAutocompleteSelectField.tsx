import Chip from "@material-ui/core/Chip";
import MenuItem from "@material-ui/core/MenuItem";
import Paper from "@material-ui/core/Paper";
import { withStyles } from "@material-ui/core/styles";
import TextField from "@material-ui/core/TextField";
import Downshift, { ControllerStateAndHelpers } from "downshift";
import * as React from "react";

import i18n from "../../i18n";
import ArrowDropdownIcon from "../../icons/ArrowDropdown";

interface ChoiceType {
  label: string;
  value: string;
}
interface MultiAutocompleteSelectFieldProps {
  name: string;
  choices: ChoiceType[];
  value?: ChoiceType[];
  loading?: boolean;
  placeholder?: string;
  helperText?: string;
  label?: string;
  fetchChoices(value: string);
  onChange(event);
}

const decorate = withStyles(theme => ({
  chip: {
    margin: `${theme.spacing.unit / 2}px ${theme.spacing.unit / 2}px`
  },
  container: {
    flexGrow: 1,
    position: "relative" as "relative"
  },
  inputRoot: {
    flexWrap: "wrap" as "wrap"
  },
  paper: {
    left: 0,
    marginTop: theme.spacing.unit,
    position: "absolute" as "absolute",
    right: 0,
    zIndex: 1
  }
}));

export const MultiAutocompleteSelectField = decorate<
  MultiAutocompleteSelectFieldProps
>(
  ({
    choices,
    classes,
    helperText,
    label,
    loading,
    name,
    placeholder,
    value,
    fetchChoices,
    onChange
  }) => {
    const handleSelect = (
      item: ChoiceType,
      { reset }: ControllerStateAndHelpers
    ) => {
      reset({ inputValue: "" });
      onChange({ target: { name, value: [...value, item] } });
    };
    const handleDelete = (item: ChoiceType) => () => {
      value.splice(value.indexOf(item), 1);
      onChange({ target: { name, value } });
    };
    const handleKeyDown = (inputValue: string | null) => (
      event: React.KeyboardEvent<any>
    ) => {
      switch (event.keyCode) {
        // Backspace
        case 8:
          if (!inputValue) {
            onChange({
              target: {
                name,
                value: value.slice(0, value.length - 1)
              }
            });
            break;
          }
      }
    };

    const filteredChoices = choices.filter(
      suggestion => value.map(v => v.value).indexOf(suggestion.value) === -1
    );

    return (
      <Downshift
        selectedItem={value}
        itemToString={item => (item ? item.label : "")}
        onSelect={handleSelect}
        onInputValueChange={fetchChoices}
      >
        {({
          getInputProps,
          getItemProps,
          isOpen,
          inputValue,
          selectedItem,
          highlightedIndex
        }) => {
          return (
            <div className={classes.container}>
              <TextField
                InputProps={{
                  classes: {
                    root: classes.inputRoot
                  },
                  ...getInputProps({
                    onKeyDown: handleKeyDown(inputValue),
                    placeholder
                  }),
                  endAdornment: <ArrowDropdownIcon />,
                  startAdornment: selectedItem.map(item => (
                    <Chip
                      key={item.value}
                      tabIndex={-1}
                      label={item.label}
                      className={classes.chip}
                      onDelete={handleDelete(item)}
                    />
                  ))
                }}
                helperText={helperText}
                label={label}
                fullWidth={true}
              />
              {isOpen && (
                <Paper className={classes.paper} square>
                  {loading ? (
                    <MenuItem disabled={true} component="div">
                      {i18n.t("Loading...")}
                    </MenuItem>
                  ) : (
                    <>
                      {filteredChoices.length > 0
                        ? filteredChoices.map((suggestion, index) => (
                            <MenuItem
                              key={suggestion.value}
                              selected={highlightedIndex === index}
                              component="div"
                              {...getItemProps({ item: suggestion })}
                            >
                              {suggestion.label}
                            </MenuItem>
                          ))
                        : !loading && (
                            <MenuItem disabled={true} component="div">
                              {i18n.t("No results found")}
                            </MenuItem>
                          )}
                    </>
                  )}
                </Paper>
              )}
            </div>
          );
        }}
      </Downshift>
    );
  }
);
MultiAutocompleteSelectField.displayName = "MultiAutocompleteSelectField";
export default MultiAutocompleteSelectField;
