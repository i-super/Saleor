import Card from "@material-ui/core/Card";
import CardContent from "@material-ui/core/CardContent";
import { withStyles } from "@material-ui/core/styles";
import TextField from "@material-ui/core/TextField";
import * as React from "react";

import { FormSpacer } from "../../../components/FormSpacer";
import PriceField from "../../../components/PriceField";
import { RichTextEditor } from "../../../components/RichTextEditor";
import i18n from "../../../i18n";

interface ProductDetailsFormProps {
  currencySymbol?: string;
  description?: string;
  disabled?: boolean;
  errors: { [key: string]: string };
  name?: string;
  price?: number;
  onChange(event: any);
}

const decorate = withStyles(theme => ({
  root: {
    display: "grid",
    gridTemplateColumns: `1fr ${theme.spacing.unit}px 8rem`
  }
}));

export const ProductDetailsForm = decorate<ProductDetailsFormProps>(
  ({
    classes,
    currencySymbol,
    description,
    disabled,
    errors,
    name,
    onChange,
    price
  }) => (
    <Card>
      <CardContent>
        <div className={classes.root}>
          <TextField
            error={!!errors.name}
            helperText={errors.name}
            disabled={disabled}
            fullWidth
            key="nameInput"
            label={i18n.t("Name")}
            name="name"
            rows={5}
            value={name}
            onChange={onChange}
          />
          <span />
          <PriceField
            error={!!errors.price}
            name="price"
            hint={errors.price}
            currencySymbol={currencySymbol}
            disabled={disabled}
            key="priceInput"
            label={i18n.t("Price")}
            onChange={onChange}
            value={price}
          />
        </div>
        <FormSpacer />
        <RichTextEditor
          error={!!errors.description}
          disabled={disabled}
          fullWidth
          helperText={
            errors.description
              ? errors.description
              : i18n.t("Select text to enable text-formatting tools.")
          }
          key="descriptionInput"
          label={i18n.t("Description")}
          name="description"
          value={description}
          onChange={onChange}
        />
      </CardContent>
    </Card>
  )
);
export default ProductDetailsForm;
