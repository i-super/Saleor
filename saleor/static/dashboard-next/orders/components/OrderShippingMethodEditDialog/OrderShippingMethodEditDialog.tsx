import Button from "material-ui/Button";
import Dialog, {
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogProps,
  DialogTitle
} from "material-ui/Dialog";
import { InputAdornment } from "material-ui/Input";
import { withStyles } from "material-ui/styles";
import TextField from "material-ui/TextField";
import Typography from "material-ui/Typography";
import * as React from "react";

import { SingleAutocompleteSelectField } from "../../../components/SingleAutocompleteSelectField";
import i18n from "../../../i18n";

interface OrderShippingMethodEditDialogProps {
  open: boolean;
  shippingMethod?: {
    label: string;
    value: string;
  };
  shippingMethods?: Array<{
    id: string;
    name: string;
    country: string;
  }>;
  loading?: boolean;
  fetchShippingMethods(value: string);
  onChange(event: React.ChangeEvent<any>);
  onClose?();
  onConfirm?(event: React.FormEvent<any>);
}

const decorate = withStyles(theme => ({
  dialog: {
    overflowY: "visible" as "visible"
  },
  root: {
    overflowY: "visible" as "visible",
    width: theme.breakpoints.values.sm
  },
  select: {
    flex: 1,
    marginRight: theme.spacing.unit * 2
  },
  textRight: {
    textAlign: "right" as "right"
  }
}));
const OrderShippingMethodEditDialog = decorate<
  OrderShippingMethodEditDialogProps
>(
  ({
    classes,
    open,
    loading,
    shippingMethod,
    shippingMethods,
    fetchShippingMethods,
    onChange,
    onClose,
    onConfirm
  }) => {
    const choices =
      !loading && shippingMethods
        ? shippingMethods.map(s => ({
            label: `${s.name} (${s.country})`,
            value: s.id
          }))
        : [];
    return (
      <Dialog open={open} classes={{ paper: classes.dialog }}>
        <DialogTitle>{i18n.t("Edit customer details")}</DialogTitle>
        <DialogContent className={classes.root}>
          <SingleAutocompleteSelectField
            choices={choices}
            loading={loading}
            name="user"
            value={shippingMethod}
            fetchChoices={fetchShippingMethods}
            onChange={onChange}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>
            {i18n.t("Cancel", { context: "button" })}
          </Button>
          <Button color="primary" variant="raised" onClick={onConfirm}>
            {i18n.t("Confirm", { context: "button" })}
          </Button>
        </DialogActions>
      </Dialog>
    );
  }
);
export default OrderShippingMethodEditDialog;
