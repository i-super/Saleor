import Button from "@material-ui/core/Button";
import Dialog, { DialogProps } from "@material-ui/core/Dialog";
import DialogActions from "@material-ui/core/DialogActions";
import DialogContent from "@material-ui/core/DialogContent";
import DialogContentText from "@material-ui/core/DialogContentText";
import DialogTitle from "@material-ui/core/DialogTitle";
import { withStyles } from "@material-ui/core/styles";
import * as React from "react";

import i18n from "../../../i18n";

const decorate = withStyles(theme => ({
  deleteButton: {
    "&:hover": {
      backgroundColor: theme.palette.error.main
    },
    backgroundColor: theme.palette.error.main,
    color: theme.palette.error.contrastText
  }
}));

export interface ProductVariantDeleteDialogProps {
  open: boolean;
  name: string;
  onClose?();
  onConfirm?();
}

const ProductVariantDeleteDialog = decorate<ProductVariantDeleteDialogProps>(
  props => {
    const { children, classes, name, open, onConfirm, onClose } = props;
    return (
      <Dialog open={open}>
        <DialogTitle>
          {i18n.t("Delete variant", { context: "title" })}
        </DialogTitle>
        <DialogContent>
          <DialogContentText
            dangerouslySetInnerHTML={{
              __html: i18n.t(
                "Are you sure you want to remove <strong>{{name}}</strong>?",
                { name }
              )
            }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>
            {i18n.t("Cancel", { context: "button" })}
          </Button>
          <Button
            className={classes.deleteButton}
            variant="raised"
            onClick={onConfirm}
          >
            {i18n.t("Delete variant", { context: "button" })}
          </Button>
        </DialogActions>
      </Dialog>
    );
  }
);

export default ProductVariantDeleteDialog;
